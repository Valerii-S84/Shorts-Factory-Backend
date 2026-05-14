from __future__ import annotations

from typing import Protocol

from shorts_factory.db.models import JobStatus, PublishPlatform, RecordStatus, VideoJob
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.publishing.telegram_publisher import PublishResult
from shorts_factory.publishing.youtube_publisher import YouTubePublishError, YouTubePublishResult


class DuplicatePublishError(RuntimeError):
    pass


class TelegramVideoPublisher(Protocol):
    def publish_video(self, *, video_path: str, caption: str) -> PublishResult:
        pass


class YouTubeVideoPublisher(Protocol):
    def publish_video(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
    ) -> YouTubePublishResult:
        pass


class PublishService:
    def __init__(
        self,
        repository: VideoJobRepository,
        telegram_publisher: TelegramVideoPublisher | None = None,
        youtube_publisher: YouTubeVideoPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._telegram_publisher = telegram_publisher
        self._youtube_publisher = youtube_publisher

    def publish_to_telegram(self, job: VideoJob) -> VideoJob:
        if self._telegram_publisher is None:
            raise ValueError("Telegram publisher is not configured.")
        if self._repository.has_successful_publish(job, PublishPlatform.TELEGRAM):
            raise DuplicatePublishError("Telegram publish already succeeded for this job.")
        if job.video_path is None:
            raise ValueError("Job does not have a rendered video.")
        if job.script_json is None:
            raise ValueError("Job does not have script metadata.")

        result = self._telegram_publisher.publish_video(
            video_path=job.video_path,
            caption=str(job.script_json["telegram_caption"]),
        )
        self._repository.add_publish_log(
            job,
            platform=PublishPlatform.TELEGRAM,
            status=RecordStatus.SUCCESS,
            external_id=result.external_id,
            url=result.url,
        )
        return self._repository.update_status(job, JobStatus.TELEGRAM_PUBLISHED)

    def publish_to_youtube(self, job: VideoJob) -> VideoJob:
        if self._youtube_publisher is None:
            raise ValueError("YouTube publisher is not configured.")
        if self._repository.has_successful_publish(job, PublishPlatform.YOUTUBE):
            raise DuplicatePublishError("YouTube publish already succeeded for this job.")
        if job.video_path is None:
            raise ValueError("Job does not have a rendered video.")
        if job.script_json is None:
            raise ValueError("Job does not have script metadata.")

        try:
            result = self._youtube_publisher.publish_video(
                video_path=job.video_path,
                title=str(job.script_json["youtube_title"]),
                description=str(job.script_json.get("youtube_description", "")),
            )
        except YouTubePublishError as error:
            self._repository.add_publish_log(
                job,
                platform=PublishPlatform.YOUTUBE,
                status=RecordStatus.FAILED,
                error_message=str(error),
            )
            raise

        self._repository.add_publish_log(
            job,
            platform=PublishPlatform.YOUTUBE,
            status=RecordStatus.SUCCESS,
            external_id=result.external_id,
            url=result.url,
            metadata={"privacy_status": result.privacy_status},
        )
        return self._repository.update_status(job, JobStatus.YOUTUBE_PUBLISHED)
