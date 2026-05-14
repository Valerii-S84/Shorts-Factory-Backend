import pytest
from pydantic import ValidationError

from shorts_factory.settings import Settings


def test_local_settings_can_start_without_secrets() -> None:
    settings = Settings(environment="local")

    assert settings.app_name == "Shorts Factory Backend"
    assert settings.database_url is None
    assert settings.effective_database_url == "sqlite+pysqlite:///var/shorts_factory.db"
    assert settings.api_key is None


def test_production_settings_require_database_url_and_api_key() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(environment="production")

    message = str(error.value)
    assert "DATABASE_URL" in message
    assert "SHORTS_FACTORY_API_KEY" in message


def test_api_key_is_secret_value() -> None:
    settings = Settings(environment="test", api_key="super-secret")

    assert str(settings.api_key) == "**********"
    assert settings.api_key.get_secret_value() == "super-secret"


def test_youtube_settings_keep_access_token_secret() -> None:
    settings = Settings(environment="test", youtube_access_token="youtube-token")

    assert settings.youtube_privacy_status == "private"
    assert settings.youtube_category_id == "27"
    assert str(settings.youtube_access_token) == "**********"
    assert settings.youtube_access_token.get_secret_value() == "youtube-token"
