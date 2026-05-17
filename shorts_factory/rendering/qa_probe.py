from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from shorts_factory.generation.schemas import FrameType
from shorts_factory.generation.voiceover_script import VOICEOVER_TOTAL_DURATION_SEC
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.production_templates import (
    PRODUCTION_DURATION_MAX_SEC,
    PRODUCTION_DURATION_MIN_SEC,
    get_template,
    validate_production_frame_order,
)
from shorts_factory.rendering.render_plan import RenderPlan
from shorts_factory.settings import Settings


class QAError(RuntimeError):
    pass


class VideoProbe(BaseModel):
    path: str
    width: int
    height: int
    duration_sec: float
    has_audio: bool
    audio_duration_sec: float | None = None


class QAResult(BaseModel):
    passed: bool
    probe: VideoProbe


class FFprobeVideoProbe:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def probe(self, video_path: str) -> VideoProbe:
        command = [
            self._settings.ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            video_path,
        ]
        result = subprocess.run(command, capture_output=True, check=False, text=True)
        if result.returncode != 0:
            raise QAError(result.stderr.strip() or "ffprobe failed.")
        return parse_ffprobe_output(video_path, result.stdout)


def parse_ffprobe_output(video_path: str, output: str) -> VideoProbe:
    payload = json.loads(output)
    streams = payload.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video_stream is None:
        raise QAError("Video stream is missing.")

    duration = payload.get("format", {}).get("duration") or video_stream.get("duration")
    if duration is None:
        raise QAError("Video duration is missing.")

    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    audio_duration = _stream_duration(audio_stream) if audio_stream else None

    return VideoProbe(
        path=video_path,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        duration_sec=float(duration),
        has_audio=audio_stream is not None,
        audio_duration_sec=audio_duration,
    )


class VideoQAService:
    def __init__(self, probe: FFprobeVideoProbe) -> None:
        self._probe = probe

    def validate(
        self,
        *,
        video_path: str,
        quiz: Quiz,
        render_plan: RenderPlan,
    ) -> QAResult:
        _validate_static_requirements(video_path, quiz, render_plan)
        probe = self._probe.probe(video_path)
        _validate_probe(probe)
        return QAResult(passed=True, probe=probe)


def _validate_static_requirements(video_path: str, quiz: Quiz, render_plan: RenderPlan) -> None:
    path = Path(video_path)
    if not path.exists():
        raise QAError("Video file is missing.")
    if path.suffix.lower() != ".mp4":
        raise QAError("Video file must be MP4.")
    if not render_plan.has_text_overlays:
        raise QAError("Render plan does not contain text overlays.")
    if render_plan.correct_option_label != quiz.correct_option_label:
        raise QAError("Correct answer label does not match Quiz Bank.")
    if render_plan.correct_answer_text != quiz.correct_option.text:
        raise QAError("Correct answer text does not match Quiz Bank.")
    if not render_plan.telegram_caption:
        raise QAError("Telegram caption is missing.")
    if not render_plan.youtube_title:
        raise QAError("YouTube title is missing.")
    _validate_audio_asset(render_plan)
    _validate_voiceover_requirements(quiz, render_plan)
    _validate_creative_requirements(render_plan)


def _validate_probe(probe: VideoProbe) -> None:
    if probe.width != 1080 or probe.height != 1920:
        raise QAError("Video must be 1080x1920.")
    if not PRODUCTION_DURATION_MIN_SEC <= probe.duration_sec <= PRODUCTION_DURATION_MAX_SEC:
        raise QAError("Video duration must be within the 15.5 second accepted range.")
    if not probe.has_audio:
        raise QAError("Video audio stream is missing.")
    if probe.audio_duration_sec is not None and probe.audio_duration_sec > probe.duration_sec + 0.2:
        raise QAError("Video audio stream is longer than the rendered video duration.")


def _validate_creative_requirements(render_plan: RenderPlan) -> None:
    template = _template(render_plan)
    frame_sequence = render_plan.frame_sequence
    try:
        validate_production_frame_order(frame_sequence)
    except ValueError as error:
        raise QAError(str(error)) from error

    answer_frame = _frame(render_plan, FrameType.ANSWER)

    _validate_duration(render_plan)
    _validate_answer_reveal(render_plan, template.answer_reveal_at_sec, answer_frame)
    _validate_answer_not_visible_before_reveal(render_plan)
    _validate_explanation(render_plan, answer_frame)
    _validate_overflow(render_plan)

    question_frame = _frame(render_plan, FrameType.QUESTION)
    options_frame = _frame(render_plan, FrameType.OPTIONS)
    if not question_frame.text_overlay.text.strip():
        raise QAError("Question frame is missing.")
    if not options_frame.text_overlay.text.strip():
        raise QAError("Options frame is missing.")


def _template(render_plan: RenderPlan):
    try:
        return get_template(render_plan.template_id)
    except ValueError as error:
        raise QAError(str(error)) from error


def _frame(render_plan: RenderPlan, frame_type: FrameType):
    for frame in render_plan.frames:
        if frame.type == frame_type:
            return frame
    raise QAError(f"{frame_type.value} frame is missing.")


def _validate_duration(render_plan: RenderPlan) -> None:
    if not PRODUCTION_DURATION_MIN_SEC <= render_plan.duration_sec <= PRODUCTION_DURATION_MAX_SEC:
        raise QAError("Render plan duration must be within the 15.5 second accepted range.")
    metadata = render_plan.creative_metadata
    if metadata.template_id != render_plan.template_id:
        raise QAError("Creative metadata template_id does not match render plan.")


def _validate_answer_reveal(
    render_plan: RenderPlan, expected_reveal_sec: float, answer_frame
) -> None:
    actual_reveal_sec = answer_frame.starts_at_sec
    if abs(actual_reveal_sec - expected_reveal_sec) > 0.01:
        raise QAError("Answer reveal starts outside the allowed timing.")
    if abs(render_plan.answer_reveal_at_sec - expected_reveal_sec) > 0.01:
        raise QAError("Render plan answer reveal timing is invalid.")


def _validate_answer_not_visible_before_reveal(render_plan: RenderPlan) -> None:
    for frame in render_plan.frames:
        if frame.type == FrameType.ANSWER:
            return
        if render_plan.answer_reveal_text in frame.text_overlay.text:
            raise QAError("Answer reveal is visible before the answer segment.")


def _validate_explanation(render_plan: RenderPlan, answer_frame) -> None:
    if not render_plan.explanation_text.strip():
        raise QAError("Answer explanation is missing.")
    if render_plan.explanation_text not in answer_frame.text_overlay.text:
        raise QAError("Answer frame must include the explanation.")


def _validate_overflow(render_plan: RenderPlan) -> None:
    if any(frame.text_overlay.has_overflow_risk for frame in render_plan.frames):
        raise QAError("Text overlay overflow risk is not controlled.")


def _validate_audio_asset(render_plan: RenderPlan) -> None:
    audio_path = Path(render_plan.audio_path)
    if not audio_path.exists():
        raise QAError("Audio file is missing.")
    if audio_path.stat().st_size == 0:
        raise QAError("Audio file is empty.")
    if audio_path.suffix.lower() != ".mp3":
        raise QAError("Voiceover audio file must be MP3.")
    if not render_plan.audio_checksum:
        raise QAError("Audio checksum is missing.")


def _validate_voiceover_requirements(quiz: Quiz, render_plan: RenderPlan) -> None:
    if not render_plan.has_voiceover:
        raise QAError("Render plan voiceover flag is missing.")
    if render_plan.voice_model != "gpt-4o-mini-tts":
        raise QAError("Voice model does not match the canonical TTS model.")
    if render_plan.voice_id not in {"cedar", "marin"}:
        raise QAError("Voice id is not an allowed canonical or fallback voice.")
    if abs(render_plan.voice_speed - 0.8) > 0.001:
        raise QAError("Voice speed does not match the canonical TTS speed.")
    if render_plan.narration_parts_count != 3 or len(render_plan.narration_parts) != 3:
        raise QAError("Voiceover narration must contain exactly 3 parts.")
    if render_plan.narration_estimated_duration_sec > VOICEOVER_TOTAL_DURATION_SEC:
        raise QAError("Voiceover estimated duration is longer than the video.")
    if not render_plan.narration_contains_question:
        raise QAError("Voiceover narration is missing the question.")
    if not render_plan.narration_contains_all_options:
        raise QAError("Voiceover narration is missing one or more answer options.")
    if not render_plan.narration_contains_correct_answer:
        raise QAError("Voiceover narration is missing the correct answer.")
    _validate_narration_text(quiz, render_plan.narration_parts)


def _validate_narration_text(quiz: Quiz, narration_parts: list[str]) -> None:
    question_part, options_part, answer_part = narration_parts
    if quiz.question not in question_part:
        raise QAError("Voiceover question part does not contain the Quiz Bank question.")
    for option in quiz.options:
        if f"{option.label}: {option.text}" not in options_part:
            raise QAError("Voiceover options part is missing an answer option.")
    answer_phrase = f"Richtig ist {quiz.correct_option_label}: {quiz.correct_option.text}"
    if answer_phrase not in answer_part:
        raise QAError("Voiceover answer part does not contain the correct answer.")
    if answer_phrase in question_part or answer_phrase in options_part:
        raise QAError("Voiceover reveals the answer before the answer part.")


def _stream_duration(stream: dict[str, object]) -> float | None:
    duration = stream.get("duration")
    try:
        return float(duration) if duration is not None else None
    except (TypeError, ValueError):
        return None
