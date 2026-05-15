from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from shorts_factory.generation.schemas import FrameType, GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.text_overlay import TextOverlay
from shorts_factory.settings import Settings
from shorts_factory.storage.asset_paths import job_asset_path

FRAME_DURATIONS = {
    FrameType.HOOK: 2.0,
    FrameType.QUESTION: 4.0,
    FrameType.OPTIONS: 5.0,
    FrameType.PAUSE: 3.0,
    FrameType.ANSWER: 3.0,
    FrameType.CTA: 1.0,
}


class RenderFrame(BaseModel):
    type: FrameType
    image_path: str
    duration_sec: float
    text_overlay: TextOverlay


class RenderPlan(BaseModel):
    job_id: int
    quiz_id: str
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration_sec: float = 18.0
    audio_path: str
    output_path: str
    frames: list[RenderFrame] = Field(min_length=1)
    correct_option_label: str
    correct_answer_text: str
    telegram_caption: str
    youtube_title: str

    @property
    def has_text_overlays(self) -> bool:
        return all(frame.text_overlay.text for frame in self.frames)


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

    output_path = job_asset_path(settings, job_id, "videos", "short.mp4")
    frames = [
        RenderFrame(
            type=frame.type,
            image_path=str(image_paths[index]),
            duration_sec=FRAME_DURATIONS.get(frame.type, 3.0),
            text_overlay=TextOverlay(text=_overlay_text(frame.type, frame.text, quiz)),
        )
        for index, frame in enumerate(script.frames)
    ]

    duration = sum(frame.duration_sec for frame in frames)
    return RenderPlan(
        job_id=job_id,
        quiz_id=quiz.quiz_id,
        duration_sec=duration,
        audio_path=str(audio_path),
        output_path=str(output_path),
        frames=frames,
        correct_option_label=quiz.correct_option_label,
        correct_answer_text=quiz.correct_option.text,
        telegram_caption=script.telegram_caption,
        youtube_title=script.youtube_title,
    )


def _overlay_text(frame_type: FrameType, generated_text: str, quiz: Quiz) -> str:
    if frame_type == FrameType.QUESTION:
        return quiz.question
    if frame_type == FrameType.OPTIONS:
        return "\n".join(f"{option.label} {option.text}" for option in quiz.options)
    if frame_type == FrameType.ANSWER:
        return f"Richtig ist: {quiz.correct_option_label} {quiz.correct_option.text}"
    return generated_text
