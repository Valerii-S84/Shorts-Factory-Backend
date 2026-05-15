from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from shorts_factory.generation.schemas import FrameType
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.production_templates import (
    CTA_MIN_DURATION_SEC,
    PRODUCTION_DURATION_MAX_SEC,
    PRODUCTION_DURATION_MIN_SEC,
    get_template,
    validate_production_frame_order,
)
from shorts_factory.rendering.render_plan import RenderPlan
from shorts_factory.rendering.text_overlay import OverlayKind
from shorts_factory.settings import Settings


class QAError(RuntimeError):
    pass


class VideoProbe(BaseModel):
    path: str
    width: int
    height: int
    duration_sec: float
    has_audio: bool


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

    return VideoProbe(
        path=video_path,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        duration_sec=float(duration),
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
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
    _validate_creative_requirements(render_plan)


def _validate_probe(probe: VideoProbe) -> None:
    if probe.width != 1080 or probe.height != 1920:
        raise QAError("Video must be 1080x1920.")
    if not PRODUCTION_DURATION_MIN_SEC <= probe.duration_sec <= PRODUCTION_DURATION_MAX_SEC:
        raise QAError("Video duration must be between 16 and 18 seconds.")
    if not probe.has_audio:
        raise QAError("Video audio stream is missing.")


def _validate_creative_requirements(render_plan: RenderPlan) -> None:
    template = _template(render_plan)
    frame_sequence = render_plan.frame_sequence
    try:
        validate_production_frame_order(frame_sequence)
    except ValueError as error:
        raise QAError(str(error)) from error

    hook_frame = _frame(render_plan, FrameType.HOOK)
    pause_frame = _frame(render_plan, FrameType.PAUSE)
    answer_frame = _frame(render_plan, FrameType.ANSWER)
    cta_frame = _frame(render_plan, FrameType.CTA)

    _validate_duration(render_plan)
    _validate_variants(render_plan, template)
    _validate_countdown(render_plan, pause_frame)
    _validate_answer_reveal(render_plan, template.answer_reveal_at_sec, answer_frame)
    _validate_answer_not_visible_before_reveal(render_plan)
    _validate_explanation(render_plan, answer_frame)
    _validate_cta(cta_frame)
    _validate_overflow(render_plan)

    if not hook_frame.text_overlay.text.strip():
        raise QAError("Hook frame is missing.")


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
        raise QAError("Render plan duration must be between 16 and 18 seconds.")


def _validate_variants(render_plan: RenderPlan, template) -> None:
    hook_ids = {variant.variant_id for variant in template.allowed_hook_variants}
    if render_plan.hook_variant_id not in hook_ids:
        raise QAError("Hook variant is not allowed for the production template.")
    if render_plan.cta_variant_id not in template.allowed_cta_variant_ids:
        raise QAError("CTA variant is not allowed for the production template.")
    metadata = render_plan.creative_metadata
    if metadata.template_id != render_plan.template_id:
        raise QAError("Creative metadata template_id does not match render plan.")
    if metadata.hook_variant_id != render_plan.hook_variant_id:
        raise QAError("Creative metadata hook_variant_id does not match render plan.")
    if metadata.cta_variant_id != render_plan.cta_variant_id:
        raise QAError("Creative metadata cta_variant_id does not match render plan.")


def _validate_countdown(render_plan: RenderPlan, pause_frame) -> None:
    if not render_plan.has_countdown:
        raise QAError("Countdown is missing.")
    if pause_frame.text_overlay.kind != OverlayKind.COUNTDOWN:
        raise QAError("Pause frame must use countdown overlay.")
    if pause_frame.text_overlay.countdown_values != ("3", "2", "1"):
        raise QAError("Countdown overlay must include 3, 2, 1.")


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


def _validate_cta(cta_frame) -> None:
    if not cta_frame.text_overlay.text.strip():
        raise QAError("CTA frame is missing.")
    if cta_frame.duration_sec < CTA_MIN_DURATION_SEC:
        raise QAError("CTA duration must be at least 2 seconds.")


def _validate_overflow(render_plan: RenderPlan) -> None:
    if any(frame.text_overlay.has_overflow_risk for frame in render_plan.frames):
        raise QAError("Text overlay overflow risk is not controlled.")
