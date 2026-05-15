from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["local", "test", "development", "staging", "production"]
YouTubePrivacyStatus = Literal["private", "unlisted", "public"]
LOCAL_DATABASE_URL = "sqlite+pysqlite:///var/shorts_factory.db"
QUIZ_BANK_DEFAULT_CONSUMER_ID = "shorts_factory_backend"
QUIZ_BANK_DEFAULT_NEXT_PATH = "/v1/quiz-items/next"
QUIZ_BANK_DEFAULT_LANGUAGE = "de"


class Settings(BaseSettings):
    app_name: str = Field(
        default="Shorts Factory Backend", validation_alias="SHORTS_FACTORY_APP_NAME"
    )
    environment: Environment = Field(default="local", validation_alias="SHORTS_FACTORY_ENV")
    log_level: str = Field(default="INFO", validation_alias="SHORTS_FACTORY_LOG_LEVEL")
    media_root: Path = Field(
        default=Path("var/media"), validation_alias="SHORTS_FACTORY_MEDIA_ROOT"
    )
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    api_key: SecretStr | None = Field(default=None, validation_alias="SHORTS_FACTORY_API_KEY")
    quiz_bank_base_url: str | None = Field(default=None, validation_alias="QUIZ_BANK_BASE_URL")
    quiz_bank_edge_api_key: SecretStr | None = Field(
        default=None, validation_alias="QUIZ_BANK_EDGE_API_KEY"
    )
    quiz_bank_consumer_id: str = Field(
        default=QUIZ_BANK_DEFAULT_CONSUMER_ID, validation_alias="QUIZ_BANK_CONSUMER_ID"
    )
    quiz_bank_api_key: SecretStr | None = Field(default=None, validation_alias="QUIZ_BANK_API_KEY")
    quiz_bank_quota_key: SecretStr | None = Field(
        default=None, validation_alias="QUIZ_BANK_QUOTA_KEY"
    )
    quiz_bank_next_path: str = Field(
        default=QUIZ_BANK_DEFAULT_NEXT_PATH, validation_alias="QUIZ_BANK_NEXT_PATH"
    )
    quiz_bank_default_levels: Annotated[list[str], NoDecode] = Field(
        default_factory=list, validation_alias="QUIZ_BANK_DEFAULT_LEVELS"
    )
    quiz_bank_default_themes: Annotated[list[str], NoDecode] = Field(
        default_factory=list, validation_alias="QUIZ_BANK_DEFAULT_THEMES"
    )
    quiz_bank_default_language: str = Field(
        default=QUIZ_BANK_DEFAULT_LANGUAGE, validation_alias="QUIZ_BANK_DEFAULT_LANGUAGE"
    )
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_script_model: str = Field(
        default="gpt-4o-2024-08-06", validation_alias="OPENAI_SCRIPT_MODEL"
    )
    openai_image_model: str = Field(default="gpt-image-1", validation_alias="OPENAI_IMAGE_MODEL")
    openai_tts_model: str = Field(default="gpt-4o-mini-tts", validation_alias="OPENAI_TTS_MODEL")
    openai_voice: str = Field(default="alloy", validation_alias="OPENAI_VOICE")
    telegram_bot_token: SecretStr | None = Field(
        default=None, validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")
    ffmpeg_path: str = Field(default="ffmpeg", validation_alias="FFMPEG_PATH")
    ffprobe_path: str = Field(default="ffprobe", validation_alias="FFPROBE_PATH")
    youtube_access_token: SecretStr | None = Field(
        default=None, validation_alias="YOUTUBE_ACCESS_TOKEN"
    )
    youtube_upload_url: str = Field(
        default="https://www.googleapis.com/upload/youtube/v3/videos",
        validation_alias="YOUTUBE_UPLOAD_URL",
    )
    youtube_privacy_status: YouTubePrivacyStatus = Field(
        default="private", validation_alias="YOUTUBE_PRIVACY_STATUS"
    )
    youtube_category_id: str = Field(default="27", validation_alias="YOUTUBE_CATEGORY_ID")

    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def require_production_configuration(self) -> Settings:
        if self.environment != "production":
            return self

        missing = []
        if self.database_url is None:
            missing.append("DATABASE_URL")
        if self.api_key is None:
            missing.append("SHORTS_FACTORY_API_KEY")
        if self.quiz_bank_base_url is None:
            missing.append("QUIZ_BANK_BASE_URL")
        if self.quiz_bank_edge_api_key is None:
            missing.append("QUIZ_BANK_EDGE_API_KEY")
        if not self.quiz_bank_consumer_id.strip():
            missing.append("QUIZ_BANK_CONSUMER_ID")
        if self.quiz_bank_api_key is None:
            missing.append("QUIZ_BANK_API_KEY")
        if self.openai_api_key is None:
            missing.append("OPENAI_API_KEY")
        if self.telegram_bot_token is None:
            missing.append("TELEGRAM_BOT_TOKEN")
        if self.telegram_chat_id is None:
            missing.append("TELEGRAM_CHAT_ID")

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required production configuration: {joined}.")

        return self

    @field_validator("quiz_bank_default_levels", "quiz_bank_default_themes", mode="before")
    @classmethod
    def parse_quiz_bank_selection(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def effective_database_url(self) -> str | None:
        if self.database_url is not None:
            return self.database_url
        if self.environment in {"local", "test", "development"}:
            return LOCAL_DATABASE_URL
        return None

    @property
    def videos_root(self) -> Path:
        return self.media_root / "videos"

    @property
    def images_root(self) -> Path:
        return self.media_root / "images"

    @property
    def audio_root(self) -> Path:
        return self.media_root / "audio"


@lru_cache
def get_settings() -> Settings:
    return Settings()
