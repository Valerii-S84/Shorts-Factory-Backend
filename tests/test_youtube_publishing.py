from pathlib import Path

import httpx
import pytest

from shorts_factory.db.models import Base, JobStatus, PublishPlatform, RecordStatus
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.publishing.publish_service import PublishService
from shorts_factory.publishing.youtube_publisher import (
    YouTubePublisher,
    YouTubePublishError,
    YouTubePublishResult,
)
from shorts_factory.settings import Settings


class SuccessfulYouTubePublisher:
    def publish_video(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
    ) -> YouTubePublishResult:
        return YouTubePublishResult(
            external_id="youtube-123",
            url="https://www.youtube.com/watch?v=youtube-123",
            privacy_status="private",
        )


class FailingYouTubePublisher:
    def publish_video(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
    ) -> YouTubePublishResult:
        raise YouTubePublishError("YouTube upload failed with status 503.")


def test_youtube_publisher_uploads_private_video_and_returns_url(tmp_path: Path) -> None:
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert request.headers["authorization"] == "Bearer token"
        assert request.url.params["part"] == "snippet,status"
        assert request.url.params["uploadType"] == "multipart"
        assert b"Deutsch Quiz" in body
        assert b'"privacyStatus": "private"' in body
        return httpx.Response(
            200,
            json={"id": "youtube-123", "status": {"privacyStatus": "private"}},
        )

    publisher = YouTubePublisher(
        Settings(environment="test", youtube_access_token="token"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = publisher.publish_video(
        video_path=str(video_path),
        title="Deutsch Quiz",
        description="Beschreibung",
    )

    assert result.external_id == "youtube-123"
    assert result.url == "https://www.youtube.com/watch?v=youtube-123"
    assert result.privacy_status == "private"


def test_youtube_publisher_requires_access_token() -> None:
    with pytest.raises(YouTubePublishError):
        YouTubePublisher(Settings(environment="test"))


def test_publish_service_publishes_youtube_and_records_metadata(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = _job_ready_for_publish(repository, tmp_path)

        service = PublishService(repository, youtube_publisher=SuccessfulYouTubePublisher())
        service.publish_to_youtube(job)

        completed_job = repository.get_with_children(job.id)
        publish_log = completed_job.publish_logs[0]
        assert completed_job.status == JobStatus.YOUTUBE_PUBLISHED.value
        assert publish_log.platform == PublishPlatform.YOUTUBE.value
        assert publish_log.status == RecordStatus.SUCCESS.value
        assert publish_log.external_id == "youtube-123"
        assert publish_log.metadata_json == {"privacy_status": "private"}
    finally:
        session.close()
        engine.dispose()


def test_failed_youtube_publish_keeps_previous_job_status(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = _job_ready_for_publish(repository, tmp_path)
        repository.update_status(job, JobStatus.TELEGRAM_PUBLISHED)

        with pytest.raises(YouTubePublishError):
            service = PublishService(repository, youtube_publisher=FailingYouTubePublisher())
            service.publish_to_youtube(job)

        completed_job = repository.get_with_children(job.id)
        publish_log = completed_job.publish_logs[0]
        assert completed_job.status == JobStatus.TELEGRAM_PUBLISHED.value
        assert publish_log.platform == PublishPlatform.YOUTUBE.value
        assert publish_log.status == RecordStatus.FAILED.value
        assert publish_log.error_message == "YouTube upload failed with status 503."
    finally:
        session.close()
        engine.dispose()


def _repository(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    return VideoJobRepository(session), session, engine


def _job_ready_for_publish(repository: VideoJobRepository, tmp_path: Path):
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    job = repository.create(target_platforms=[PublishPlatform.YOUTUBE.value])
    repository.store_script(
        job,
        {
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Beschreibung",
        },
    )
    repository.store_video_result(job, video_path=str(video_path), duration_sec=18.0)
    repository.update_status(job, JobStatus.QA_PASSED)
    return job
