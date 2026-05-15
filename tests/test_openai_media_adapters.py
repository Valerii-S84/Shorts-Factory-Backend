from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_factory.generation.image_generator import ImageGenerationError, OpenAIImageGenerator
from shorts_factory.generation.image_style_contract import PRODUCTION_IMAGE_STYLE_CONTRACT
from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.generation.voice_generator import OpenAIVoiceGenerator, VoiceGenerationError
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


def test_openai_image_generator_writes_decoded_images(tmp_path: Path) -> None:
    client = FakeImageClient("aW1hZ2U=")
    generator = OpenAIImageGenerator(_settings(tmp_path), storage=LocalStorage(), client=client)

    paths = generator.generate(job_id=7, script=valid_script())

    assert len(paths) == 6
    assert all(path.read_bytes() == b"image" for path in paths)
    assert client.calls[0]["prompt"] != "German classroom with a curious student"
    assert "German classroom with a curious student" in client.calls[0]["prompt"]
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


def test_openai_voice_generator_streams_audio_file(tmp_path: Path) -> None:
    client = FakeVoiceClient()
    generator = OpenAIVoiceGenerator(_settings(tmp_path), client=client)

    path = generator.generate(job_id=7, script=valid_script())

    assert path.read_bytes() == b"voice"
    assert client.streaming.calls[0]["model"] == "tts-test"
    assert client.streaming.calls[0]["input"] == valid_script().voiceover


def test_openai_voice_generator_requires_api_key() -> None:
    with pytest.raises(VoiceGenerationError, match="OPENAI_API_KEY"):
        OpenAIVoiceGenerator(Settings(environment="test"))


class FakeImageClient:
    def __init__(self, b64_json: str | None) -> None:
        self.calls = []
        self.images = SimpleNamespace(generate=self.generate)
        self._b64_json = b64_json

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self._b64_json)])


class FakeStreamingResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def stream_to_file(self, path: Path) -> None:
        Path(path).write_bytes(b"voice")


class FakeStreamingResponses:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStreamingResponse()


class FakeVoiceClient:
    def __init__(self) -> None:
        self.streaming = FakeStreamingResponses()
        self.audio = SimpleNamespace(speech=SimpleNamespace(with_streaming_response=self.streaming))


def _settings(media_root: Path) -> Settings:
    return Settings(
        environment="test",
        media_root=media_root,
        openai_api_key="key",
        openai_image_model="image-test",
        openai_tts_model="tts-test",
    )


def valid_script() -> GeneratedScript:
    return GeneratedScript.model_validate(
        {
            "hook": "Kannst du das lösen?",
            "voiceover": "Was bedeutet 'Haus'? Richtig ist A, house.",
            "frames": [
                {
                    "type": "hook",
                    "text": "Hook",
                    "image_prompt": "German classroom with a curious student",
                },
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
                    "type": "pause",
                    "text": "3\n2\n1",
                    "image_prompt": "Student thinking before choosing",
                },
                {
                    "type": "answer",
                    "text": "Richtig ist: A house",
                    "image_prompt": "Happy student learning vocabulary",
                },
                {
                    "type": "cta",
                    "text": "Mehr Deutsch-Quiz im Telegram-Kanal",
                    "image_prompt": "Friendly study desk with a smartphone",
                },
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )
