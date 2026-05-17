from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_factory.generation.voice_generator import OpenAIVoiceGenerator, VoiceGenerationError
from shorts_factory.generation.voiceover_script import build_voiceover_plan
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings


def test_openai_voice_generator_falls_back_to_marin_when_cedar_is_unavailable(
    tmp_path: Path,
) -> None:
    client = FakeVoiceClient(cedar_error=RuntimeError("cedar voice unavailable"))
    generator = OpenAIVoiceGenerator(settings(tmp_path), client=client)

    voiceover = generator.generate(job_id=9, voiceover_plan=build_voiceover_plan(quiz()))

    assert voiceover.voice_id == "marin"
    assert voiceover.path.read_bytes() == b"voice"
    assert [call["voice"] for call in client.streaming.calls] == ["cedar", "marin"]


def test_openai_voice_generator_wraps_fallback_failure(tmp_path: Path) -> None:
    client = FakeVoiceClient(
        cedar_error=RuntimeError("cedar voice unavailable"),
        fallback_error=RuntimeError("marin also failed"),
    )
    generator = OpenAIVoiceGenerator(settings(tmp_path), client=client)

    with pytest.raises(VoiceGenerationError, match="marin also failed"):
        generator.generate(job_id=9, voiceover_plan=build_voiceover_plan(quiz()))


def test_openai_voice_generator_rejects_empty_output_file(tmp_path: Path) -> None:
    client = FakeVoiceClient(response_bytes=b"")
    generator = OpenAIVoiceGenerator(settings(tmp_path), client=client)

    with pytest.raises(VoiceGenerationError, match="non-empty audio"):
        generator.generate(job_id=9, voiceover_plan=build_voiceover_plan(quiz()))


def test_openai_voice_generator_wraps_non_fallback_errors(tmp_path: Path) -> None:
    client = FakeVoiceClient(cedar_error=RuntimeError("network failed"))
    generator = OpenAIVoiceGenerator(settings(tmp_path), client=client)

    with pytest.raises(VoiceGenerationError, match="network failed"):
        generator.generate(job_id=9, voiceover_plan=build_voiceover_plan(quiz()))


class FakeStreamingResponse:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def __enter__(self) -> FakeStreamingResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def stream_to_file(self, path: Path) -> None:
        Path(path).write_bytes(self._content)


class FakeStreamingResponses:
    def __init__(
        self,
        *,
        response_bytes: bytes = b"voice",
        cedar_error: Exception | None = None,
        fallback_error: Exception | None = None,
    ) -> None:
        self.calls = []
        self._response_bytes = response_bytes
        self._cedar_error = cedar_error
        self._fallback_error = fallback_error

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["voice"] == "cedar" and self._cedar_error is not None:
            raise self._cedar_error
        if kwargs["voice"] == "marin" and self._fallback_error is not None:
            raise self._fallback_error
        return FakeStreamingResponse(self._response_bytes)


class FakeVoiceClient:
    def __init__(
        self,
        *,
        response_bytes: bytes = b"voice",
        cedar_error: Exception | None = None,
        fallback_error: Exception | None = None,
    ) -> None:
        self.streaming = FakeStreamingResponses(
            response_bytes=response_bytes,
            cedar_error=cedar_error,
            fallback_error=fallback_error,
        )
        self.audio = SimpleNamespace(speech=SimpleNamespace(with_streaming_response=self.streaming))


def settings(tmp_path: Path) -> Settings:
    return Settings(environment="test", media_root=tmp_path, openai_api_key="key")


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-voice-fallback",
            "question": "Welche Antwort passt?",
            "options": [{"label": "A", "text": "ja"}, {"label": "B", "text": "nein"}],
            "correct_answer": "A",
            "explanation": "Ja passt hier.",
            "level": "A2",
            "topic": "Alltag",
            "status": "approved",
        }
    )
