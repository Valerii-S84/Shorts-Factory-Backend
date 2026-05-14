from __future__ import annotations

from shorts_factory.db.models import JobStatus, PublishPlatform, RecordStatus, VideoJob
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.publishing.telegram_publisher import TelegramPublisher


class DuplicatePublishError(RuntimeError):
    pass


class PublishService:
    def __init__(
        self, repository: VideoJobRepository, telegram_publisher: TelegramPublisher
    ) -> None:
        self._repository = repository
        self._telegram_publisher = telegram_publisher

    def publish_to_telegram(self, job: VideoJob) -> VideoJob:
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
