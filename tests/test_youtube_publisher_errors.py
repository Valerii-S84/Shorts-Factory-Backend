from pathlib import Path

import httpx
import pytest

from shorts_factory.publishing.youtube_publisher import YouTubePublisher, YouTubePublishError
from shorts_factory.settings import Settings


def test_youtube_publisher_wraps_http_status_errors(tmp_path: Path) -> None:
    video_path = _video(tmp_path)
    publisher = _publisher(lambda request: httpx.Response(503, request=request))

    with pytest.raises(YouTubePublishError, match="status 503"):
        publisher.publish_video(video_path=str(video_path), title="Deutsch Quiz", description="")


def test_youtube_publisher_wraps_transport_errors(tmp_path: Path) -> None:
    video_path = _video(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    publisher = _publisher(handler)

    with pytest.raises(YouTubePublishError, match="request failed"):
        publisher.publish_video(video_path=str(video_path), title="Deutsch Quiz", description="")


def test_youtube_publisher_rejects_response_without_video_id(tmp_path: Path) -> None:
    video_path = _video(tmp_path)
    publisher = _publisher(lambda request: httpx.Response(200, json={"status": {}}))

    with pytest.raises(YouTubePublishError, match="video id"):
        publisher.publish_video(video_path=str(video_path), title="Deutsch Quiz", description="")


@pytest.mark.parametrize(
    ("filename", "title", "message"),
    [
        ("missing.mp4", "Deutsch Quiz", "Video file does not exist"),
        ("short.mov", "Deutsch Quiz", "requires an MP4"),
        ("short.mp4", "  ", "title is required"),
    ],
)
def test_youtube_publisher_rejects_invalid_video_requests(
    tmp_path: Path, filename: str, title: str, message: str
) -> None:
    video_path = tmp_path / filename
    if filename != "missing.mp4":
        video_path.write_bytes(b"video")
    publisher = _publisher(lambda request: httpx.Response(500, request=request))

    with pytest.raises(YouTubePublishError, match=message):
        publisher.publish_video(video_path=str(video_path), title=title, description="")


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "youtube-123"},
        {"id": "youtube-123", "status": {"privacyStatus": "unsupported"}},
    ],
)
def test_youtube_publisher_falls_back_to_configured_privacy(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    video_path = _video(tmp_path)
    publisher = YouTubePublisher(
        Settings(
            environment="test", youtube_access_token="token", youtube_privacy_status="unlisted"
        ),
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        ),
    )

    result = publisher.publish_video(
        video_path=str(video_path), title="Deutsch Quiz", description=""
    )

    assert result.privacy_status == "unlisted"


def _publisher(handler) -> YouTubePublisher:
    return YouTubePublisher(
        Settings(environment="test", youtube_access_token="token"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _video(tmp_path: Path) -> Path:
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    return video_path
