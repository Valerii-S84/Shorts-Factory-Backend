from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from shorts_factory.generation.schemas import FrameType, GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.production_templates import (
    CreativeSelection,
    select_creative,
    validate_production_frame_order,
)
from shorts_factory.rendering.text_overlay import OverlayKind, TextOverlay, build_text_overlay
from shorts_factory.settings import Settings
from shorts_factory.storage.asset_paths import job_asset_path

EXPLANATION_MAX_CHARS = 90


class RenderFrame(BaseModel):
    type: FrameType
    image_path: str
    duration_sec: float
    starts_at_sec: float = 0.0
    text_overlay: TextOverlay


class CreativeMetadata(BaseModel):
    video_id: str
    job_id: int
    quiz_id: str
    level: str | None
    topic: str | None
    template_id: str
    hook_variant_id: str
    cta_variant_id: str
    duration_sec: float
    frame_sequence: list[str]
    answer_reveal_at_sec: float
    has_countdown: bool
    has_voiceover: bool
    has_music: bool
    has_sfx: bool
    platform: str | None = None
    publish_url: str | None = None


class RenderPlan(BaseModel):
    job_id: int
    quiz_id: str
    level: str | None = None
    topic: str | None = None
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration_sec: float = 18.0
    audio_path: str
    output_path: str
    frames: list[RenderFrame] = Field(min_length=1)
    template_id: str
    hook_variant_id: str
    cta_variant_id: str
    answer_reveal_at_sec: float
    has_countdown: bool
    has_voiceover: bool = True
    has_music: bool = False
    has_sfx: bool = False
    answer_reveal_text: str
    explanation_text: str
    correct_option_label: str
    correct_answer_text: str
    telegram_caption: str
    youtube_title: str
    creative_metadata: CreativeMetadata

    @property
    def has_text_overlays(self) -> bool:
        return all(frame.text_overlay.text for frame in self.frames)

    @property
    def frame_sequence(self) -> tuple[FrameType, ...]:
        return tuple(frame.type for frame in self.frames)


def build_render_plan(
    *,
    settings: Settings,
    job_id: int,
    quiz: Quiz,
    script: GeneratedScript,
    image_paths: list[Path],
    audio_path: Path,
) -> RenderPlan:
    if len(image_paths) < len(script.frames):
        raise ValueError("Render plan requires one image per script frame.")

    frame_types = tuple(frame.type for frame in script.frames)
    validate_production_frame_order(frame_types)

    selection = select_creative(job_id=job_id, quiz_level=quiz.level, quiz_topic=quiz.topic)
    output_path = job_asset_path(settings, job_id, "videos", "short.mp4")
    answer_reveal_text = f"Richtig: {quiz.correct_option_label} {quiz.correct_option.text}"
    explanation_text = safe_explanation_excerpt(quiz.explanation)

    frames = []
    starts_at_sec = 0.0
    for index, frame in enumerate(script.frames):
        duration_sec = selection.template.durations[frame.type]
        frames.append(
            RenderFrame(
                type=frame.type,
                image_path=str(image_paths[index]),
                duration_sec=duration_sec,
                starts_at_sec=starts_at_sec,
                text_overlay=build_text_overlay(
                    _overlay_kind(frame.type),
                    _overlay_text(frame.type, frame.text, quiz, selection, explanation_text),
                ),
            )
        )
        starts_at_sec += duration_sec

    duration = sum(frame.duration_sec for frame in frames)
    metadata = CreativeMetadata(
        video_id=f"job-{job_id}",
        job_id=job_id,
        quiz_id=quiz.quiz_id,
        level=quiz.level,
        topic=quiz.topic,
        template_id=selection.template.template_id,
        hook_variant_id=selection.hook_variant.variant_id,
        cta_variant_id=selection.cta_variant.variant_id,
        duration_sec=duration,
        frame_sequence=[frame.type.value for frame in frames],
        answer_reveal_at_sec=selection.template.answer_reveal_at_sec,
        has_countdown=selection.template.countdown_required,
        has_voiceover=True,
        has_music=False,
        has_sfx=False,
    )
    return RenderPlan(
        job_id=job_id,
        quiz_id=quiz.quiz_id,
        level=quiz.level,
        topic=quiz.topic,
        duration_sec=duration,
        audio_path=str(audio_path),
        output_path=str(output_path),
        frames=frames,
        template_id=selection.template.template_id,
        hook_variant_id=selection.hook_variant.variant_id,
        cta_variant_id=selection.cta_variant.variant_id,
        answer_reveal_at_sec=selection.template.answer_reveal_at_sec,
        has_countdown=selection.template.countdown_required,
        has_voiceover=True,
        has_music=False,
        has_sfx=False,
        answer_reveal_text=answer_reveal_text,
        explanation_text=explanation_text,
        correct_option_label=quiz.correct_option_label,
        correct_answer_text=quiz.correct_option.text,
        telegram_caption=script.telegram_caption,
        youtube_title=script.youtube_title,
        creative_metadata=metadata,
    )


def safe_explanation_excerpt(explanation: str, max_chars: int = EXPLANATION_MAX_CHARS) -> str:
    stripped = " ".join(explanation.strip().split())
    if len(stripped) <= max_chars:
        return stripped

    sentence_match = re.match(r"^(.+?[.!?])\s+", stripped)
    if sentence_match and len(sentence_match.group(1)) <= max_chars:
        return sentence_match.group(1)

    excerpt = stripped[: max_chars + 1]
    if " " in excerpt:
        excerpt = excerpt[: excerpt.rfind(" ")]
    return excerpt.rstrip(" ,;:") + "..."


def _overlay_text(
    frame_type: FrameType,
    generated_text: str,
    quiz: Quiz,
    selection: CreativeSelection,
    explanation_text: str,
) -> str:
    if frame_type == FrameType.HOOK:
        return selection.hook_variant.text
    if frame_type == FrameType.QUESTION:
        return quiz.question
    if frame_type == FrameType.OPTIONS:
        return "\n".join(f"{option.label}  {option.text}" for option in quiz.options)
    if frame_type == FrameType.PAUSE:
        return "3\n2\n1"
    if frame_type == FrameType.ANSWER:
        answer_line = f"Richtig: {quiz.correct_option_label} {quiz.correct_option.text}"
        return f"{answer_line}\n{explanation_text}"
    if frame_type == FrameType.CTA:
        return selection.cta_variant.text
    return generated_text


def _overlay_kind(frame_type: FrameType) -> OverlayKind:
    if frame_type == FrameType.HOOK:
        return OverlayKind.HOOK
    if frame_type == FrameType.QUESTION:
        return OverlayKind.QUESTION
    if frame_type == FrameType.OPTIONS:
        return OverlayKind.OPTIONS
    if frame_type == FrameType.PAUSE:
        return OverlayKind.COUNTDOWN
    if frame_type == FrameType.ANSWER:
        return OverlayKind.ANSWER
    if frame_type == FrameType.CTA:
        return OverlayKind.CTA
    raise ValueError(f"Unsupported frame type: {frame_type}")
