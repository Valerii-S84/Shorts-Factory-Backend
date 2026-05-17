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


def test_openai_image_settings_use_production_defaults() -> None:
    settings = Settings(environment="test")

    assert settings.openai_image_model == "gpt-image-1"
    assert settings.openai_image_size == "1024x1536"
    assert settings.openai_image_quality == "high"
    assert settings.openai_image_background == "opaque"
    assert settings.openai_image_output_format == "png"
    assert settings.openai_image_moderation == "auto"
    assert settings.openai_voice_speed == 0.8


def test_openai_image_settings_can_be_overridden_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "image-env")
    monkeypatch.setenv("OPENAI_IMAGE_SIZE", "1536x1024")
    monkeypatch.setenv("OPENAI_IMAGE_QUALITY", "medium")
    monkeypatch.setenv("OPENAI_IMAGE_BACKGROUND", "transparent")
    monkeypatch.setenv("OPENAI_IMAGE_OUTPUT_FORMAT", "webp")
    monkeypatch.setenv("OPENAI_IMAGE_MODERATION", "low")

    settings = Settings(environment="test")

    assert settings.openai_image_model == "image-env"
    assert settings.openai_image_size == "1536x1024"
    assert settings.openai_image_quality == "medium"
    assert settings.openai_image_background == "transparent"
    assert settings.openai_image_output_format == "webp"
    assert settings.openai_image_moderation == "low"


def test_youtube_settings_keep_access_token_secret() -> None:
    settings = Settings(environment="test", youtube_access_token="youtube-token")

    assert settings.youtube_privacy_status == "private"
    assert settings.youtube_category_id == "27"
    assert str(settings.youtube_access_token) == "**********"
    assert settings.youtube_access_token.get_secret_value() == "youtube-token"


def test_quiz_bank_settings_use_runtime_defaults_and_secret_values() -> None:
    settings = Settings(
        environment="test",
        quiz_bank_base_url="https://api.valerchik.de",
        quiz_bank_edge_api_key="edge-token",
        quiz_bank_api_key="bank-token",
        quiz_bank_quota_key="quota-token",
    )

    assert settings.quiz_bank_base_url == "https://api.valerchik.de"
    assert settings.quiz_bank_next_path == "/v1/quiz-items/next"
    assert settings.quiz_bank_consumer_id == "shorts_factory_backend"
    assert settings.quiz_bank_default_levels == []
    assert settings.quiz_bank_default_themes == []
    assert settings.quiz_bank_default_language == "de"
    assert str(settings.quiz_bank_edge_api_key) == "**********"
    assert str(settings.quiz_bank_api_key) == "**********"
    assert str(settings.quiz_bank_quota_key) == "**********"


def test_quiz_bank_selection_settings_parse_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("QUIZ_BANK_DEFAULT_LEVELS", "custom-level-1,custom-level-2")
    monkeypatch.setenv("QUIZ_BANK_DEFAULT_THEMES", "custom-theme")

    settings = Settings(environment="test")

    assert settings.quiz_bank_default_levels == ["custom-level-1", "custom-level-2"]
    assert settings.quiz_bank_default_themes == ["custom-theme"]
