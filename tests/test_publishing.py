from pathlib import Path

import httpx

from shorts_factory.publishing.telegram_publisher import TelegramPublisher
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
