from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "development", "staging", "production"]
LOCAL_DATABASE_URL = "sqlite+pysqlite:///var/shorts_factory.db"


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

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required production configuration: {joined}.")

        return self

    @property
    def effective_database_url(self) -> str | None:
        if self.database_url is not None:
            return self.database_url
        if self.environment in {"local", "test", "development"}:
            return LOCAL_DATABASE_URL
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
