from __future__ import annotations

import json
from pathlib import Path

import httpx
from pydantic import BaseModel

from shorts_factory.settings import Settings, YouTubePrivacyStatus


class YouTubePublishError(RuntimeError):
    pass


class YouTubePublishResult(BaseModel):
    external_id: str
    url: str
    privacy_status: YouTubePrivacyStatus


class YouTubePublisher:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        if settings.youtube_access_token is None:
            raise YouTubePublishError("YOUTUBE_ACCESS_TOKEN is not configured.")
        self._settings = settings
        self._client = http_client or httpx.Client(timeout=300)

    def publish_video(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
    ) -> YouTubePublishResult:
        path = Path(video_path)
        _validate_video_request(path, title)

        try:
            payload = self._upload_video(path, title=title, description=description)
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            raise YouTubePublishError(
                f"YouTube upload failed with status {status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise YouTubePublishError("YouTube upload request failed.") from error

        video_id = payload.get("id")
        if not isinstance(video_id, str) or not video_id:
            raise YouTubePublishError("YouTube upload response did not include a video id.")

        privacy_status = _privacy_status(payload, self._settings.youtube_privacy_status)
        return YouTubePublishResult(
            external_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            privacy_status=privacy_status,
        )

    def _upload_video(self, path: Path, *, title: str, description: str) -> dict[str, object]:
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": self._settings.youtube_category_id,
            },
            "status": {"privacyStatus": self._settings.youtube_privacy_status},
        }
        token = self._settings.youtube_access_token.get_secret_value()
        headers = {"Authorization": f"Bearer {token}"}
        params = {"part": "snippet,status", "uploadType": "multipart"}
        with path.open("rb") as video_file:
            response = self._client.post(
                self._settings.youtube_upload_url,
                headers=headers,
                params=params,
                files={
                    "metadata": (
                        "metadata.json",
                        json.dumps(metadata),
                        "application/json; charset=UTF-8",
                    ),
                    "video": (path.name, video_file, "video/mp4"),
                },
            )
        response.raise_for_status()
        return response.json()


def _validate_video_request(path: Path, title: str) -> None:
    if not path.exists():
        raise YouTubePublishError("Video file does not exist.")
    if path.suffix.lower() != ".mp4":
        raise YouTubePublishError("YouTube publish requires an MP4 video.")
    if not title.strip():
        raise YouTubePublishError("YouTube title is required.")


def _privacy_status(
    payload: dict[str, object],
    fallback: YouTubePrivacyStatus,
) -> YouTubePrivacyStatus:
    status_payload = payload.get("status")
    if not isinstance(status_payload, dict):
        return fallback

    value = status_payload.get("privacyStatus")
    if value in {"private", "unlisted", "public"}:
        return value
    return fallback
