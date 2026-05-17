from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from shorts_factory.generation.schemas import FrameType, GeneratedScript
from shorts_factory.generation.voiceover_script import (
    VoiceoverPlan,
    build_voiceover_plan,
    validate_voiceover_plan,
)
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.production_templates import (
    CreativeSelection,
    select_creative,
    validate_production_frame_order,
)
from shorts_factory.rendering.text_overlay import (
    OVERLAY_TEMPLATES,
    OverlayKind,
    TextOverlay,
    build_text_overlay,
    wrapped_overlay_lines,
)
from shorts_factory.settings import Settings
from shorts_factory.storage.asset_paths import job_asset_path

EXPLANATION_MAX_CHARS = 90
ANSWER_OVERLAY_TARGET_MAX_LINES = 4
ANSWER_EXPLANATION_MAX_LINES = 2
EXPLANATION_FALLBACK_CHAR_LIMITS = (72, 64, 56, 48, 40, 32, 24, 18)
EXPLANATION_BOUNDARY_MIN_CHARS = 12


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
    duration_sec: float
    frame_sequence: list[str]
    answer_reveal_at_sec: float
    has_countdown: bool
    has_voiceover: bool
    has_music: bool
    has_sfx: bool
    voice_model: str
    voice_id: str
    voice_speed: float
    audio_path: str
    audio_checksum: str | None = None
    narration_parts_count: int
    narration_contains_question: bool
    narration_contains_all_options: bool
    narration_contains_correct_answer: bool
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
    audio_checksum: str | None = None
    output_path: str
    frames: list[RenderFrame] = Field(min_length=1)
    template_id: str
    answer_reveal_at_sec: float
    has_countdown: bool
    has_voiceover: bool = True
    has_music: bool = False
    has_sfx: bool = False
    voice_model: str
    voice_id: str
    voice_speed: float
    narration_text: str
    narration_parts: list[str] = Field(min_length=3, max_length=3)
    narration_estimated_duration_sec: float
    narration_parts_count: int
    narration_contains_question: bool
    narration_contains_all_options: bool
    narration_contains_correct_answer: bool
    audio_trim_policy: str = "trim_or_pad_to_video_duration"
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
    audio_checksum: str | None = None,
    voiceover_plan: VoiceoverPlan | None = None,
    voice_model: str | None = None,
    voice_id: str | None = None,
    voice_speed: float | None = None,
) -> RenderPlan:
    if len(image_paths) < len(script.frames):
        raise ValueError("Render plan requires one image per script frame.")

    frame_types = tuple(frame.type for frame in script.frames)
    validate_production_frame_order(frame_types)
    narration = voiceover_plan or build_voiceover_plan(quiz, speed=settings.openai_tts_speed)
    validate_voiceover_plan(narration, quiz)

    selection = select_creative(job_id=job_id, quiz_level=quiz.level, quiz_topic=quiz.topic)
    output_path = job_asset_path(settings, job_id, "videos", "short.mp4")
    answer_reveal_text = f"Richtig: {quiz.correct_option_label} {quiz.correct_option.text}"
    explanation_text = safe_explanation_excerpt(quiz.explanation, answer_line=answer_reveal_text)

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
        duration_sec=duration,
        frame_sequence=[frame.type.value for frame in frames],
        answer_reveal_at_sec=selection.template.answer_reveal_at_sec,
        has_countdown=False,
        has_voiceover=True,
        has_music=False,
        has_sfx=False,
        voice_model=voice_model or settings.openai_tts_model,
        voice_id=voice_id or settings.openai_tts_voice,
        voice_speed=voice_speed or settings.openai_tts_speed,
        audio_path=str(audio_path),
        audio_checksum=audio_checksum,
        narration_parts_count=len(narration.parts),
        narration_contains_question=narration.narration_contains_question,
        narration_contains_all_options=narration.narration_contains_all_options,
        narration_contains_correct_answer=narration.narration_contains_correct_answer,
    )
    return RenderPlan(
        job_id=job_id,
        quiz_id=quiz.quiz_id,
        level=quiz.level,
        topic=quiz.topic,
        duration_sec=duration,
        audio_path=str(audio_path),
        audio_checksum=audio_checksum,
        output_path=str(output_path),
        frames=frames,
        template_id=selection.template.template_id,
        answer_reveal_at_sec=selection.template.answer_reveal_at_sec,
        has_countdown=False,
        has_voiceover=True,
        has_music=False,
        has_sfx=False,
        voice_model=voice_model or settings.openai_tts_model,
        voice_id=voice_id or settings.openai_tts_voice,
        voice_speed=voice_speed or settings.openai_tts_speed,
        narration_text=narration.text,
        narration_parts=[part.text for part in narration.parts],
        narration_estimated_duration_sec=narration.estimated_duration_sec,
        narration_parts_count=len(narration.parts),
        narration_contains_question=narration.narration_contains_question,
        narration_contains_all_options=narration.narration_contains_all_options,
        narration_contains_correct_answer=narration.narration_contains_correct_answer,
        answer_reveal_text=answer_reveal_text,
        explanation_text=explanation_text,
        correct_option_label=quiz.correct_option_label,
        correct_answer_text=quiz.correct_option.text,
        telegram_caption=script.telegram_caption,
        youtube_title=script.youtube_title,
        creative_metadata=metadata,
    )


def safe_explanation_excerpt(
    explanation: str,
    max_chars: int = EXPLANATION_MAX_CHARS,
    *,
    answer_line: str | None = None,
) -> str:
    stripped = " ".join(explanation.strip().split())
    if answer_line is None:
        return _trim_explanation_at_boundary(stripped, max_chars)

    template = OVERLAY_TEMPLATES[OverlayKind.ANSWER]
    answer_line_count = len(wrapped_overlay_lines(answer_line, template.max_line_chars))
    available_lines = min(
        ANSWER_EXPLANATION_MAX_LINES,
        max(1, ANSWER_OVERLAY_TARGET_MAX_LINES - answer_line_count),
    )
    safe_available_lines = max(1, template.max_lines - answer_line_count)
    return _fit_explanation_excerpt(
        stripped,
        max_chars=max_chars,
        max_line_chars=template.max_line_chars,
        max_lines=min(available_lines, safe_available_lines),
    )


def _fit_explanation_excerpt(
    explanation: str, *, max_chars: int, max_line_chars: int, max_lines: int
) -> str:
    for char_limit in _descending_char_limits(max_chars):
        excerpt = _trim_explanation_at_boundary(explanation, char_limit)
        if len(wrapped_overlay_lines(excerpt, max_line_chars)) <= max_lines:
            return excerpt

    shortest = _trim_explanation_at_boundary(explanation, min(max_chars, max_line_chars))
    if len(wrapped_overlay_lines(shortest, max_line_chars)) <= max_lines:
        return shortest
    return wrapped_overlay_lines(shortest, max_line_chars)[0]


def _descending_char_limits(max_chars: int) -> tuple[int, ...]:
    limits = {max_chars, *EXPLANATION_FALLBACK_CHAR_LIMITS}
    return tuple(sorted((limit for limit in limits if limit <= max_chars), reverse=True))


def _trim_explanation_at_boundary(explanation: str, max_chars: int) -> str:
    if len(explanation) <= max_chars:
        return explanation

    sentence_end = _last_boundary_index(explanation, max_chars, ".!?")
    if sentence_end is not None:
        return explanation[:sentence_end].rstrip()

    content_limit = max(1, max_chars - 3)
    phrase_end = _last_boundary_index(explanation, content_limit, ",;:")
    if phrase_end is not None:
        return explanation[:phrase_end].rstrip(" ,;:") + "..."

    word_end = explanation.rfind(" ", 0, content_limit + 1)
    if word_end >= EXPLANATION_BOUNDARY_MIN_CHARS:
        return explanation[:word_end].rstrip(" ,;:") + "..."
    return explanation[:content_limit].rstrip(" ,;:") + "..."


def _last_boundary_index(text: str, max_chars: int, boundary_chars: str) -> int | None:
    for index in range(min(len(text), max_chars) - 1, EXPLANATION_BOUNDARY_MIN_CHARS - 1, -1):
        if text[index] in boundary_chars and (index + 1 == len(text) or text[index + 1].isspace()):
            return index + 1
    return None


def _overlay_text(
    frame_type: FrameType,
    generated_text: str,
    quiz: Quiz,
    selection: CreativeSelection,
    explanation_text: str,
) -> str:
    if frame_type == FrameType.HOOK:
        return generated_text
    if frame_type == FrameType.QUESTION:
        return quiz.question
    if frame_type == FrameType.OPTIONS:
        return "\n".join(f"{option.label}  {option.text}" for option in quiz.options)
    if frame_type == FrameType.PAUSE:
        return generated_text
    if frame_type == FrameType.ANSWER:
        answer_line = f"Richtig: {quiz.correct_option_label} {quiz.correct_option.text}"
        return f"{answer_line}\n{explanation_text}"
    if frame_type == FrameType.CTA:
        return generated_text
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
