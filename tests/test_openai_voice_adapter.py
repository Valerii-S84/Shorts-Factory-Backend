from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_factory.generation.voice_generator import OpenAIVoiceGenerator, VoiceGenerationError
from shorts_factory.generation.voiceover_script import build_voiceover_plan
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings


def test_openai_voice_generator_streams_audio_file(tmp_path: Path) -> None:
    client = FakeVoiceClient()
    generator = OpenAIVoiceGenerator(settings(tmp_path), client=client)
    voiceover_plan = build_voiceover_plan(quiz())

    voiceover = generator.generate(job_id=7, voiceover_plan=voiceover_plan)

    assert voiceover.path == tmp_path / "audio" / "7" / "voiceover.mp3"
    assert voiceover.path.read_bytes() == b"voice"
    call = client.streaming.calls[0]
    assert call["model"] == "gpt-4o-mini-tts"
    assert call["voice"] == "cedar"
    assert call["speed"] == 0.8
    assert call["response_format"] == "mp3"
    assert call["input"] == voiceover_plan.text
    assert "speak German clearly" in call["instructions"]
    assert "calm educational tone" in call["instructions"]
    assert "natural pauses between question, options, and answer" in call["instructions"]
    assert "do not add extra words" in call["instructions"]
    assert "do not translate" in call["instructions"]
    assert "do not skip answer options" in call["instructions"]
    assert voiceover.voice_id == "cedar"


def test_openai_voice_generator_requires_api_key() -> None:
    with pytest.raises(VoiceGenerationError, match="OPENAI_API_KEY"):
        OpenAIVoiceGenerator(Settings(environment="test"))


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


def settings(tmp_path: Path) -> Settings:
    return Settings(environment="test", media_root=tmp_path, openai_api_key="key")


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-voice",
            "question": "Welche Antwort passt?",
            "options": [
                {"label": "A", "text": "heute"},
                {"label": "B", "text": "gestern"},
                {"label": "C", "text": "morgen"},
                {"label": "D", "text": "nie"},
            ],
            "correct_answer": "C",
            "explanation": "Morgen passt, weil es um die Zukunft geht.",
            "level": "A2",
            "topic": "Alltag",
            "status": "approved",
        }
    )
