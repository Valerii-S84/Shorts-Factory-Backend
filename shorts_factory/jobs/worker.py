from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shorts_factory.db.models import AssetType, JobStatus, PublishPlatform, RecordStatus
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.generation.image_generator import ImageGenerator
from shorts_factory.generation.script_generator import ScriptGenerator
from shorts_factory.generation.voice_generator import VoiceGenerator
from shorts_factory.publishing.publish_service import PublishService
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
        try:
            quiz = (
                self.quiz_bank_client.fetch_quiz(job.quiz_id)
                if job.quiz_id
                else self.quiz_bank_client.fetch_next_approved_quiz()
            )
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

            audio_path = self.voice_generator.generate(job_id=job.id, script=script)
            self.repository.add_asset(
                job,
                asset_type=AssetType.AUDIO,
                path=str(audio_path),
                checksum=self.storage.checksum(audio_path),
            )
            self.repository.update_status(job, JobStatus.AUDIO_READY)

            render_plan = build_render_plan(
                settings=self.settings,
                job_id=job.id,
                quiz=quiz,
                script=script,
                image_paths=image_paths,
                audio_path=audio_path,
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

            if PublishPlatform.TELEGRAM.value in job.target_platforms:
                self.publish_service.publish_to_telegram(job)
        except Exception as error:
            self.repository.add_render_log(
                job,
                step="worker",
                status=RecordStatus.FAILED,
                message=str(error),
            )
            self.repository.update_status(job, JobStatus.FAILED, error_message=str(error))
            raise
