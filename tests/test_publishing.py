from pathlib import Path

import httpx
import pytest

from shorts_factory.db.models import Base, JobStatus, PublishPlatform
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.publishing.publish_service import DuplicatePublishError, PublishService
from shorts_factory.publishing.telegram_publisher import (
    PublishResult,
    TelegramPublisher,
    TelegramPublishError,
)
from shorts_factory.settings import Settings


def test_telegram_publisher_posts_video_and_returns_message_url(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendVideo")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 42,
                    "chat": {"id": -100, "username": "channel"},
                },
            },
        )

    publisher = TelegramPublisher(
        Settings(
            environment="test",
            telegram_bot_token="token",
            telegram_chat_id="-100",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = publisher.publish_video(video_path=str(video_path), caption="caption")

    assert result.external_id == "42"
    assert result.chat_id == "-100"
    assert result.url == "https://t.me/channel/42"


def test_telegram_publisher_requires_token() -> None:
    with pytest.raises(TelegramPublishError, match="TELEGRAM_BOT_TOKEN"):
        TelegramPublisher(Settings(environment="test", telegram_chat_id="-100"))


def test_telegram_publisher_requires_chat_id() -> None:
    with pytest.raises(TelegramPublishError, match="TELEGRAM_CHAT_ID"):
        TelegramPublisher(Settings(environment="test", telegram_bot_token="token"))


def test_telegram_publisher_rejects_missing_video() -> None:
    publisher = TelegramPublisher(
        Settings(environment="test", telegram_bot_token="token", telegram_chat_id="-100"),
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ),
    )

    with pytest.raises(TelegramPublishError, match="Video file does not exist"):
        publisher.publish_video(video_path="missing.mp4", caption="caption")


def test_telegram_publisher_rejects_not_ok_payload(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    publisher = TelegramPublisher(
        Settings(environment="test", telegram_bot_token="token", telegram_chat_id="-100"),
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"ok": False, "description": "denied"})
            )
        ),
    )

    with pytest.raises(TelegramPublishError, match="denied"):
        publisher.publish_video(video_path=str(video_path), caption="caption")


def test_telegram_publisher_returns_no_url_without_public_username(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 42, "chat": {"id": -100}}},
        )

    publisher = TelegramPublisher(
        Settings(environment="test", telegram_bot_token="token", telegram_chat_id="-100"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = publisher.publish_video(video_path=str(video_path), caption="caption")

    assert result.url is None


class SuccessfulTelegramPublisher:
    def publish_video(self, *, video_path: str, caption: str) -> PublishResult:
        return PublishResult(external_id="telegram-123", chat_id="-100", url=None)


def test_publish_service_rejects_missing_telegram_publisher(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = _job_ready_for_telegram_publish(repository, tmp_path)

        with pytest.raises(ValueError, match="Telegram publisher is not configured"):
            PublishService(repository).publish_to_telegram(job)
    finally:
        session.close()
        engine.dispose()


def test_publish_service_rejects_duplicate_telegram_publish(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = _job_ready_for_telegram_publish(repository, tmp_path)
        service = PublishService(repository, SuccessfulTelegramPublisher())
        service.publish_to_telegram(job)

        with pytest.raises(DuplicatePublishError):
            service.publish_to_telegram(job)
    finally:
        session.close()
        engine.dispose()


def test_publish_service_rejects_telegram_publish_without_video(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        job = repository.create(target_platforms=[PublishPlatform.TELEGRAM.value])
        repository.store_script(job, {"telegram_caption": "Deutsch Quiz"})

        with pytest.raises(ValueError, match="rendered video"):
            PublishService(repository, SuccessfulTelegramPublisher()).publish_to_telegram(job)
    finally:
        session.close()
        engine.dispose()


def test_publish_service_rejects_telegram_publish_without_script(tmp_path: Path) -> None:
    repository, session, engine = _repository(tmp_path)
    try:
        video_path = tmp_path / "short.mp4"
        video_path.write_bytes(b"video")
        job = repository.create(target_platforms=[PublishPlatform.TELEGRAM.value])
        repository.store_video_result(job, video_path=str(video_path), duration_sec=18.0)

        with pytest.raises(ValueError, match="script metadata"):
            PublishService(repository, SuccessfulTelegramPublisher()).publish_to_telegram(job)
    finally:
        session.close()
        engine.dispose()


def _repository(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    return VideoJobRepository(session), session, engine


def _job_ready_for_telegram_publish(repository: VideoJobRepository, tmp_path: Path):
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    job = repository.create(target_platforms=[PublishPlatform.TELEGRAM.value])
    repository.store_script(job, {"telegram_caption": "Deutsch Quiz"})
    repository.store_video_result(job, video_path=str(video_path), duration_sec=18.0)
    repository.update_status(job, JobStatus.QA_PASSED)
    return job
