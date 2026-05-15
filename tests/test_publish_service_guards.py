from pathlib import Path

import pytest

from shorts_factory.db.models import Base, JobStatus, PublishPlatform
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.publishing.publish_service import DuplicatePublishError, PublishService
from shorts_factory.publishing.youtube_publisher import YouTubePublishResult


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


def test_publish_service_rejects_missing_youtube_publisher(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = _job_ready_for_youtube_publish(repository, tmp_path)

        with pytest.raises(ValueError, match="YouTube publisher is not configured"):
            PublishService(repository).publish_to_youtube(job)
    finally:
        session.close()
        engine.dispose()


def test_publish_service_rejects_duplicate_youtube_publish(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = _job_ready_for_youtube_publish(repository, tmp_path)
        service = PublishService(repository, youtube_publisher=SuccessfulYouTubePublisher())
        service.publish_to_youtube(job)

        with pytest.raises(DuplicatePublishError):
            service.publish_to_youtube(job)
    finally:
        session.close()
        engine.dispose()


def test_publish_service_rejects_youtube_publish_without_video(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = repository.create(target_platforms=[PublishPlatform.YOUTUBE.value])
        repository.store_script(job, {"youtube_title": "Deutsch Quiz"})

        with pytest.raises(ValueError, match="rendered video"):
            PublishService(
                repository, youtube_publisher=SuccessfulYouTubePublisher()
            ).publish_to_youtube(job)
    finally:
        session.close()
        engine.dispose()


def test_publish_service_rejects_youtube_publish_without_script(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        video_path = tmp_path / "short.mp4"
        video_path.write_bytes(b"video")
        job = repository.create(target_platforms=[PublishPlatform.YOUTUBE.value])
        repository.store_video_result(job, video_path=str(video_path), duration_sec=18.0)

        with pytest.raises(ValueError, match="script metadata"):
            PublishService(
                repository, youtube_publisher=SuccessfulYouTubePublisher()
            ).publish_to_youtube(job)
    finally:
        session.close()
        engine.dispose()


def _repository(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    return VideoJobRepository(session), session, engine


def _job_ready_for_youtube_publish(repository: VideoJobRepository, tmp_path: Path):
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    job = repository.create(target_platforms=[PublishPlatform.YOUTUBE.value])
    repository.store_script(job, {"youtube_title": "Deutsch Quiz"})
    repository.store_video_result(job, video_path=str(video_path), duration_sec=18.0)
    repository.update_status(job, JobStatus.QA_PASSED)
    return job
