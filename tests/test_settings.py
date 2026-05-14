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
