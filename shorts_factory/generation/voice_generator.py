from __future__ import annotations

from pathlib import Path
from typing import Protocol

from openai import OpenAI

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.settings import Settings
from shorts_factory.storage.asset_paths import job_asset_path


class VoiceGenerationError(RuntimeError):
    pass


class VoiceGenerator(Protocol):
    def generate(self, *, job_id: int, script: GeneratedScript) -> Path:
        pass


class OpenAIVoiceGenerator:
    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        if settings.openai_api_key is None:
            raise VoiceGenerationError("OPENAI_API_KEY is not configured.")
        self._settings = settings
        self._client = client or OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def generate(self, *, job_id: int, script: GeneratedScript) -> Path:
        path = job_asset_path(self._settings, job_id, "audio", "voiceover.mp3")
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._client.audio.speech.with_streaming_response.create(
            model=self._settings.openai_tts_model,
            voice=self._settings.openai_voice,
            input=script.voiceover,
        ) as response:
            response.stream_to_file(path)
        return path
