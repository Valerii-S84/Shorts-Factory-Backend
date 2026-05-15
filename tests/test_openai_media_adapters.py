from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_factory.generation.image_generator import ImageGenerationError, OpenAIImageGenerator
from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.generation.voice_generator import OpenAIVoiceGenerator, VoiceGenerationError
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


def test_openai_image_generator_writes_decoded_images(tmp_path: Path) -> None:
    client = FakeImageClient("aW1hZ2U=")
    generator = OpenAIImageGenerator(_settings(tmp_path), storage=LocalStorage(), client=client)

    paths = generator.generate(job_id=7, script=valid_script())

    assert len(paths) == 4
    assert all(path.read_bytes() == b"image" for path in paths)
    assert client.prompts[0] == "German classroom, warm light, clean illustration"


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
        self.prompts = []
        self.images = SimpleNamespace(generate=self.generate)
        self._b64_json = b64_json

    def generate(self, *, model: str, prompt: str, size: str):
        self.prompts.append(prompt)
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
                    "image_prompt": "German classroom, warm light, clean illustration",
                },
                {
                    "type": "question",
                    "text": "Was bedeutet 'Haus'?",
                    "image_prompt": "Student thinking in a German class, clean illustration",
                },
                {
                    "type": "options",
                    "text": "A house\nB car",
                    "image_prompt": "Quiz atmosphere in a German lesson, clean illustration",
                },
                {
                    "type": "answer",
                    "text": "Richtig ist: A house",
                    "image_prompt": "Happy student learning vocabulary, clean illustration",
                },
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )
