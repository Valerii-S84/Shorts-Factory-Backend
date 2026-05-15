from __future__ import annotations

from pathlib import Path

import httpx
from pydantic import BaseModel

from shorts_factory.settings import Settings


class TelegramPublishError(RuntimeError):
    pass


class PublishResult(BaseModel):
    external_id: str
    chat_id: str
    url: str | None = None


class TelegramPublisher:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        if settings.telegram_bot_token is None:
            raise TelegramPublishError("TELEGRAM_BOT_TOKEN is not configured.")
        if settings.telegram_chat_id is None:
            raise TelegramPublishError("TELEGRAM_CHAT_ID is not configured.")
        self._settings = settings
        self._client = http_client or httpx.Client(timeout=60)

    def publish_video(self, *, video_path: str, caption: str) -> PublishResult:
        path = Path(video_path)
        if not path.exists():
            raise TelegramPublishError("Video file does not exist.")

        token = self._settings.telegram_bot_token.get_secret_value()
        url = f"https://api.telegram.org/bot{token}/sendVideo"
        with path.open("rb") as video_file:
            response = self._client.post(
                url,
                data={"chat_id": self._settings.telegram_chat_id, "caption": caption},
                files={"video": (path.name, video_file, "video/mp4")},
            )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise TelegramPublishError(str(payload))

        result = payload["result"]
        chat = result.get("chat", {})
        return PublishResult(
            external_id=str(result["message_id"]),
            chat_id=str(chat.get("id", self._settings.telegram_chat_id)),
            url=_message_url(chat, result["message_id"]),
        )


def _message_url(chat: dict[str, object], message_id: int) -> str | None:
    username = chat.get("username")
    if isinstance(username, str) and username:
        return f"https://t.me/{username}/{message_id}"
    return None
