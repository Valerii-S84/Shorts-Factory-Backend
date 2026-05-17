from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shorts_factory.db.models import AssetType, JobStatus, PublishPlatform, RecordStatus, VideoJob
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.generation.image_generator import ImageGenerator
from shorts_factory.generation.script_generator import ScriptGenerator
from shorts_factory.generation.voice_generator import VoiceGenerator
from shorts_factory.generation.voiceover_script import build_voiceover_plan
from shorts_factory.jobs.retry_policy import RetryAction, retry_action_for_error
from shorts_factory.publishing.publish_service import PublishService
from shorts_factory.publishing.youtube_publisher import YouTubePublishError
from shorts_factory.quiz_bank.client import QuizBankClient
from shorts_factory.rendering.ffmpeg_renderer import FFmpegRenderer
from shorts_factory.rendering.qa_probe import VideoQAService
from shorts_factory.rendering.render_plan import build_render_plan
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


@dataclass(frozen=True)
class VideoJobWorker:
    settings: Settings
    repository: VideoJobRepository
    quiz_bank_client: QuizBankClient
    script_generator: ScriptGenerator
    image_generator: ImageGenerator
    voice_generator: VoiceGenerator
    renderer: FFmpegRenderer
    qa_service: VideoQAService
    publish_service: PublishService
    storage: LocalStorage

    def run(self, job_id: int) -> None:
        job = self.repository.get(job_id)
        delivery_id: str | None = None
        outcome_report_started = False
        try:
            quiz = (
                self.quiz_bank_client.fetch_quiz(job.quiz_id)
                if job.quiz_id
                else self.quiz_bank_client.fetch_next_approved_quiz()
            )
            delivery_id = quiz.delivery_id
            job.quiz_id = quiz.quiz_id
            job.level = quiz.level
            job.topic = quiz.topic
            self.repository.update_status(job, JobStatus.QUIZ_VALIDATED)

            script = self.script_generator.generate(quiz)
            self.repository.store_script(job, script.model_dump(mode="json"))
            self.repository.update_status(job, JobStatus.SCRIPT_READY)

            image_paths = self.image_generator.generate(job_id=job.id, script=script)
            for path in image_paths:
                self.repository.add_asset(
                    job,
                    asset_type=AssetType.IMAGE,
                    path=str(path),
                    checksum=self.storage.checksum(path),
                )
            self.repository.update_status(job, JobStatus.IMAGES_READY)

            voiceover_plan = build_voiceover_plan(quiz, speed=self.settings.openai_tts_speed)
            voiceover = self.voice_generator.generate(job_id=job.id, voiceover_plan=voiceover_plan)
            audio_checksum = self.storage.checksum(voiceover.path)
            self.repository.add_asset(
                job,
                asset_type=AssetType.AUDIO,
                path=str(voiceover.path),
                checksum=audio_checksum,
                metadata={
                    "audio_path": str(voiceover.path),
                    "audio_checksum": audio_checksum,
                    "voice_model": voiceover.voice_model,
                    "voice_id": voiceover.voice_id,
                    "voice_speed": voiceover.voice_speed,
                    "response_format": voiceover.response_format,
                },
            )
            self.repository.update_status(job, JobStatus.AUDIO_READY)

            render_plan = build_render_plan(
                settings=self.settings,
                job_id=job.id,
                quiz=quiz,
                script=script,
                image_paths=image_paths,
                audio_path=voiceover.path,
                audio_checksum=audio_checksum,
                voiceover_plan=voiceover_plan,
                voice_model=voiceover.voice_model,
                voice_id=voiceover.voice_id,
                voice_speed=voiceover.voice_speed,
            )
            self.repository.store_render_plan(job, render_plan.model_dump(mode="json"))
            self.repository.update_status(job, JobStatus.RENDER_PLAN_READY)

            video_path = self.renderer.render(render_plan)
            self.repository.add_asset(
                job,
                asset_type=AssetType.VIDEO,
                path=video_path,
                checksum=self.storage.checksum(Path(video_path)),
                metadata={"render_plan": render_plan.model_dump(mode="json")},
            )
            self.repository.update_status(job, JobStatus.RENDERED)

            qa_result = self.qa_service.validate(
                video_path=video_path,
                quiz=quiz,
                render_plan=render_plan,
            )
            self.repository.store_video_result(
                job,
                video_path=video_path,
                duration_sec=qa_result.probe.duration_sec,
            )
            self.repository.update_status(job, JobStatus.QA_PASSED)

            publish_failed = False
            if PublishPlatform.TELEGRAM.value in job.target_platforms:
                self.publish_service.publish_to_telegram(job)
            if PublishPlatform.YOUTUBE.value in job.target_platforms:
                try:
                    self.publish_service.publish_to_youtube(job)
                except YouTubePublishError as error:
                    publish_failed = True
                    self.repository.add_render_log(
                        job,
                        step="youtube_publish",
                        status=RecordStatus.FAILED,
                        message=str(error),
                    )
            if delivery_id is not None:
                outcome_report_started = True
                outcome = "failed" if publish_failed else "sent"
                self.quiz_bank_client.report_delivery_outcome(delivery_id, outcome)
            if not publish_failed:
                self.repository.update_status(job, JobStatus.DONE, finished=True)
        except Exception as error:
            if delivery_id is not None and not outcome_report_started:
                self._report_delivery_failed(job, delivery_id)
            self.repository.add_render_log(
                job,
                step="worker",
                status=RecordStatus.FAILED,
                message=str(error),
            )
            failure_status = _job_status_for_error(str(error), job.retry_count)
            self.repository.update_status(
                job,
                failure_status,
                error_message=str(error),
                finished=failure_status in {JobStatus.FAILED, JobStatus.MANUAL_REVIEW_REQUIRED},
            )
            raise

    def _report_delivery_failed(self, job: VideoJob, delivery_id: str) -> None:
        try:
            self.quiz_bank_client.report_delivery_outcome(delivery_id, "failed")
        except Exception as error:
            self.repository.add_render_log(
                job,
                step="delivery_outcome",
                status=RecordStatus.FAILED,
                message=str(error),
            )


def _job_status_for_error(error_message: str, retry_count: int) -> JobStatus:
    action = retry_action_for_error(error_message, retry_count)
    if action == RetryAction.RETRY:
        return JobStatus.RETRY_PENDING
    if action == RetryAction.MANUAL_REVIEW:
        return JobStatus.MANUAL_REVIEW_REQUIRED
    return JobStatus.FAILED
