from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import OpenAI

from shorts_factory.generation.voiceover_script import VoiceoverPlan
from shorts_factory.settings import OPENAI_TTS_FALLBACK_VOICE, Settings
from shorts_factory.storage.asset_paths import job_asset_path


class VoiceGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedVoiceover:
    path: Path
    voice_model: str
    voice_id: str
    voice_speed: float
    response_format: str


class VoiceGenerator(Protocol):
    def generate(self, *, job_id: int, voiceover_plan: VoiceoverPlan) -> GeneratedVoiceover:
        pass


class OpenAIVoiceGenerator:
    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        if settings.openai_api_key is None:
            raise VoiceGenerationError("OPENAI_API_KEY is not configured.")
        self._settings = settings
        self._client = client or OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def generate(self, *, job_id: int, voiceover_plan: VoiceoverPlan) -> GeneratedVoiceover:
        path = job_asset_path(
            self._settings,
            job_id,
            "audio",
            f"voiceover.{self._settings.openai_tts_response_format}",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        voice_id = self._stream_audio(
            path=path,
            voice_id=self._settings.openai_tts_voice,
            voiceover_plan=voiceover_plan,
        )
        if not path.exists() or path.stat().st_size == 0:
            raise VoiceGenerationError("OpenAI TTS did not create a non-empty audio file.")
        return GeneratedVoiceover(
            path=path,
            voice_model=self._settings.openai_tts_model,
            voice_id=voice_id,
            voice_speed=self._settings.openai_tts_speed,
            response_format=self._settings.openai_tts_response_format,
        )

    def _stream_audio(
        self,
        *,
        path: Path,
        voice_id: str,
        voiceover_plan: VoiceoverPlan,
    ) -> str:
        try:
            self._create_audio(path=path, voice_id=voice_id, voiceover_plan=voiceover_plan)
            return voice_id
        except Exception as error:
            if voice_id == "cedar" and _voice_unavailable(error):
                try:
                    self._create_audio(
                        path=path,
                        voice_id=OPENAI_TTS_FALLBACK_VOICE,
                        voiceover_plan=voiceover_plan,
                    )
                    return OPENAI_TTS_FALLBACK_VOICE
                except Exception as fallback_error:
                    raise VoiceGenerationError(str(fallback_error)) from fallback_error
            raise VoiceGenerationError(str(error)) from error

    def _create_audio(
        self,
        *,
        path: Path,
        voice_id: str,
        voiceover_plan: VoiceoverPlan,
    ) -> None:
        with self._client.audio.speech.with_streaming_response.create(
            model=self._settings.openai_tts_model,
            voice=voice_id,
            speed=self._settings.openai_tts_speed,
            response_format=self._settings.openai_tts_response_format,
            input=voiceover_plan.text,
            instructions=_tts_instructions(),
        ) as response:
            response.stream_to_file(path)


def _tts_instructions() -> str:
    return (
        "speak German clearly; calm educational tone; natural pauses between question, "
        "options, and answer; do not add extra words; do not translate; do not skip "
        "answer options"
    )


def _voice_unavailable(error: Exception) -> bool:
    message = str(error).lower()
    return "cedar" in message and any(
        marker in message for marker in ("unavailable", "unsupported", "invalid voice")
    )
