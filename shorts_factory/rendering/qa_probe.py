from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from shorts_factory.generation.schemas import FrameType
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.production_templates import (
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
    _validate_creative_requirements(render_plan, quiz)


def _validate_probe(probe: VideoProbe) -> None:
    if probe.width != 1080 or probe.height != 1920:
        raise QAError("Video must be 1080x1920.")
    if not PRODUCTION_DURATION_MIN_SEC <= probe.duration_sec <= PRODUCTION_DURATION_MAX_SEC:
        raise QAError("Video duration must be between 14 and 17 seconds.")
    if not probe.has_audio:
        raise QAError("Video audio stream is missing.")


def _validate_creative_requirements(render_plan: RenderPlan, quiz: Quiz) -> None:
    template = _template(render_plan)
    frame_sequence = render_plan.frame_sequence
    try:
        validate_production_frame_order(frame_sequence)
    except ValueError as error:
        raise QAError(str(error)) from error

    question_frame = _frame(render_plan, FrameType.QUESTION)
    options_frame = _frame(render_plan, FrameType.OPTIONS)
    answer_frame = _frame(render_plan, FrameType.ANSWER)

    _validate_duration(render_plan)
    _validate_image_count(render_plan, template.image_count)
    _validate_disabled_production_segments(render_plan)
    _validate_metadata(render_plan)
    _validate_answer_not_visible_before_reveal(render_plan)
    _validate_question_frame(question_frame, quiz)
    _validate_options_frame(options_frame, quiz)
    _validate_answer_reveal(render_plan, template.answer_reveal_at_sec, answer_frame)
    _validate_answer_frame(render_plan, answer_frame)
    _validate_explanation(render_plan, answer_frame)
    _validate_overflow(render_plan)


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
        raise QAError("Render plan duration must be between 14 and 17 seconds.")


def _validate_image_count(render_plan: RenderPlan, expected_image_count: int) -> None:
    if (
        len(render_plan.frames) != expected_image_count
        or render_plan.image_count != expected_image_count
    ):
        raise QAError("Production render plan must use exactly 3 images.")


def _validate_disabled_production_segments(render_plan: RenderPlan) -> None:
    if render_plan.has_countdown:
        raise QAError("Countdown must be disabled for the production 3-frame flow.")
    if render_plan.has_cta:
        raise QAError("CTA must be disabled for the production 3-frame flow.")


def _validate_metadata(render_plan: RenderPlan) -> None:
    metadata = render_plan.creative_metadata
    if metadata.template_id != render_plan.template_id:
        raise QAError("Creative metadata template_id does not match render plan.")
    if metadata.frame_sequence != [frame.type.value for frame in render_plan.frames]:
        raise QAError("Creative metadata frame_sequence does not match render plan.")
    if abs(metadata.answer_reveal_at_sec - render_plan.answer_reveal_at_sec) > 0.01:
        raise QAError("Creative metadata answer reveal timing is invalid.")
    if metadata.has_countdown != render_plan.has_countdown:
        raise QAError("Creative metadata countdown flag does not match render plan.")
    if metadata.has_cta != render_plan.has_cta:
        raise QAError("Creative metadata CTA flag does not match render plan.")
    if metadata.image_count != render_plan.image_count:
        raise QAError("Creative metadata image_count does not match render plan.")


def _validate_question_frame(question_frame, quiz: Quiz) -> None:
    if question_frame.text_overlay.kind != OverlayKind.QUESTION:
        raise QAError("Question frame must use question overlay.")
    if question_frame.text_overlay.text != quiz.question:
        raise QAError("Question frame must contain only the Quiz Bank question.")


def _validate_options_frame(options_frame, quiz: Quiz) -> None:
    if options_frame.text_overlay.kind != OverlayKind.OPTIONS:
        raise QAError("Options frame must use options overlay.")
    expected_options = "\n".join(f"{option.label}  {option.text}" for option in quiz.options)
    if options_frame.text_overlay.text != expected_options:
        raise QAError("Options frame must contain only the Quiz Bank answer options.")


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
        if _contains_answer_leakage(frame.text_overlay.text, render_plan):
            raise QAError("Answer reveal is visible before the answer segment.")


def _contains_answer_leakage(text: str, render_plan: RenderPlan) -> bool:
    if render_plan.answer_reveal_text in text:
        return True
    if render_plan.explanation_text and render_plan.explanation_text in text:
        return True
    return False


def _validate_answer_frame(render_plan: RenderPlan, answer_frame) -> None:
    if answer_frame.text_overlay.kind != OverlayKind.ANSWER:
        raise QAError("Answer frame must use answer overlay.")
    if render_plan.answer_reveal_text not in answer_frame.text_overlay.text:
        raise QAError("Answer frame must include the exact correct answer.")


def _validate_explanation(render_plan: RenderPlan, answer_frame) -> None:
    if not render_plan.explanation_text.strip():
        raise QAError("Answer explanation is missing.")
    if render_plan.explanation_text not in answer_frame.text_overlay.text:
        raise QAError("Answer frame must include the explanation.")


def _validate_overflow(render_plan: RenderPlan) -> None:
    if any(frame.text_overlay.has_overflow_risk for frame in render_plan.frames):
        raise QAError("Text overlay overflow risk is not controlled.")
