from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_factory.generation.image_generator import ImageGenerationError, OpenAIImageGenerator
from shorts_factory.generation.image_style_contract import PRODUCTION_IMAGE_STYLE_CONTRACT
from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


def test_openai_image_generator_writes_decoded_images(tmp_path: Path) -> None:
    client = FakeImageClient("aW1hZ2U=")
    generator = OpenAIImageGenerator(_settings(tmp_path), storage=LocalStorage(), client=client)

    paths = generator.generate(job_id=7, script=valid_script())

    assert len(paths) == 3
    assert all(path.read_bytes() == b"image" for path in paths)
    assert client.calls[0]["prompt"] != "Student thinking in a German class"
    assert "Student thinking in a German class" in client.calls[0]["prompt"]
    assert PRODUCTION_IMAGE_STYLE_CONTRACT in client.calls[0]["prompt"]
    assert client.calls[0]["model"] == "image-test"
    assert client.calls[0]["size"] == "1024x1536"
    assert client.calls[0]["quality"] == "high"
    assert client.calls[0]["background"] == "opaque"
    assert client.calls[0]["output_format"] == "png"
    assert client.calls[0]["moderation"] == "auto"


def test_openai_image_generator_builds_prompt_for_each_frame(tmp_path: Path) -> None:
    client = FakeImageClient("aW1hZ2U=")
    script = valid_script()
    generator = OpenAIImageGenerator(_settings(tmp_path), storage=LocalStorage(), client=client)

    generator.generate(job_id=7, script=script)

    assert len(client.calls) == len(script.frames)
    for frame, call in zip(script.frames, client.calls, strict=True):
        assert call["prompt"] != frame.image_prompt
        assert frame.image_prompt in call["prompt"]
        assert PRODUCTION_IMAGE_STYLE_CONTRACT in call["prompt"]
        assert "no visible text" in call["prompt"]


def test_openai_image_generator_uses_custom_image_settings(tmp_path: Path) -> None:
    client = FakeImageClient("aW1hZ2U=")
    settings = _settings(tmp_path).model_copy(
        update={
            "openai_image_model": "custom-image-model",
            "openai_image_size": "1536x1024",
            "openai_image_quality": "medium",
            "openai_image_background": "transparent",
            "openai_image_output_format": "webp",
            "openai_image_moderation": "low",
        }
    )
    generator = OpenAIImageGenerator(settings, storage=LocalStorage(), client=client)

    generator.generate(job_id=7, script=valid_script())

    assert client.calls[0]["model"] == "custom-image-model"
    assert client.calls[0]["size"] == "1536x1024"
    assert client.calls[0]["quality"] == "medium"
    assert client.calls[0]["background"] == "transparent"
    assert client.calls[0]["output_format"] == "webp"
    assert client.calls[0]["moderation"] == "low"


def test_openai_image_generator_requires_api_key() -> None:
    with pytest.raises(ImageGenerationError, match="OPENAI_API_KEY"):
        OpenAIImageGenerator(Settings(environment="test"), storage=LocalStorage())


def test_openai_image_generator_rejects_missing_b64_json(tmp_path: Path) -> None:
    generator = OpenAIImageGenerator(
        _settings(tmp_path), storage=LocalStorage(), client=FakeImageClient(None)
    )

    with pytest.raises(ImageGenerationError, match="b64_json"):
        generator.generate(job_id=7, script=valid_script())


class FakeImageClient:
    def __init__(self, b64_json: str | None) -> None:
        self.calls = []
        self.images = SimpleNamespace(generate=self.generate)
        self._b64_json = b64_json

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self._b64_json)])


def _settings(media_root: Path) -> Settings:
    return Settings(
        environment="test",
        media_root=media_root,
        openai_api_key="key",
        openai_image_model="image-test",
    )


def valid_script() -> GeneratedScript:
    return GeneratedScript.model_validate(
        {
            "frames": [
                {
                    "type": "question",
                    "text": "Was bedeutet 'Haus'?",
                    "image_prompt": "Student thinking in a German class",
                },
                {
                    "type": "options",
                    "text": "A house\nB car",
                    "image_prompt": "Learning cards on a classroom table",
                },
                {
                    "type": "answer",
                    "text": "Richtig ist: A house",
                    "image_prompt": "Happy student learning vocabulary",
                },
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )
