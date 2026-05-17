from __future__ import annotations

from pathlib import Path

import pytest

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.qa_probe import QAError, VideoProbe, VideoQAService
from shorts_factory.rendering.render_plan import RenderPlan, build_render_plan
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


def test_render_plan_stores_required_voiceover_metadata(tmp_path: Path) -> None:
    plan = render_plan(tmp_path)

    assert plan.has_voiceover
    assert plan.voice_model == "gpt-4o-mini-tts"
    assert plan.voice_id == "cedar"
    assert plan.voice_speed == 0.8
    assert plan.audio_path.endswith("audio/42/voiceover.mp3")
    assert plan.audio_checksum
    assert plan.narration_parts_count == 3
    assert plan.narration_contains_question
    assert plan.narration_contains_all_options
    assert plan.narration_contains_correct_answer


@pytest.mark.parametrize(
    ("audio_bytes", "message"),
    [(None, "Audio file is missing"), (b"", "Audio file is empty")],
)
def test_audio_qa_rejects_missing_or_empty_audio_file(
    tmp_path: Path, audio_bytes: bytes | None, message: str
) -> None:
    audio_path = tmp_path / "audio" / "42" / "voiceover.mp3"
    if audio_bytes is not None:
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(audio_bytes)
    plan = build_render_plan(
        settings=settings(tmp_path),
        job_id=42,
        quiz=quiz(),
        script=script(),
        image_paths=image_paths(tmp_path),
        audio_path=audio_path,
        audio_checksum="checksum",
    )

    with pytest.raises(QAError, match=message):
        qa(tmp_path).validate(video_path=str(video(tmp_path)), quiz=quiz(), render_plan=plan)


def test_audio_qa_rejects_answer_reveal_before_answer_part(tmp_path: Path) -> None:
    plan = render_plan(tmp_path)
    answer_phrase = f"Richtig ist {quiz().correct_option_label}: {quiz().correct_option.text}"
    parts = list(plan.narration_parts)
    parts[1] = f"{parts[1]} {answer_phrase}"
    plan = plan.model_copy(update={"narration_parts": parts})

    with pytest.raises(QAError, match="before the answer"):
        qa(tmp_path).validate(video_path=str(video(tmp_path)), quiz=quiz(), render_plan=plan)


class StaticProbe:
    def probe(self, video_path: str) -> VideoProbe:
        return VideoProbe(
            path=video_path,
            width=1080,
            height=1920,
            duration_sec=15.5,
            has_audio=True,
        )


def qa(tmp_path: Path) -> VideoQAService:
    return VideoQAService(StaticProbe())


def render_plan(tmp_path: Path) -> RenderPlan:
    audio_path, checksum = audio(tmp_path)
    return build_render_plan(
        settings=settings(tmp_path),
        job_id=42,
        quiz=quiz(),
        script=script(),
        image_paths=image_paths(tmp_path),
        audio_path=audio_path,
        audio_checksum=checksum,
    )


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-a2-termin",
            "question": "Was bedeutet 'einen Termin verschieben'?",
            "options": [
                {"label": "A", "text": "einen Termin absagen"},
                {"label": "B", "text": "einen Termin sofort beginnen"},
                {"label": "C", "text": "einen Termin auf später legen"},
                {"label": "D", "text": "zu Hause bleiben"},
            ],
            "correct_answer": "C",
            "explanation": "Man legt den Termin auf einen späteren Zeitpunkt.",
            "level": "A2",
            "topic": "Alltag",
            "status": "approved",
        }
    )


def script() -> GeneratedScript:
    return GeneratedScript.model_validate(
        {
            "frames": [
                {
                    "type": "question",
                    "text": "Was bedeutet 'einen Termin verschieben'?",
                    "image_prompt": "Calendar",
                },
                {
                    "type": "options",
                    "text": "A absagen\nB beginnen\nC später legen\nD bleiben",
                    "image_prompt": "Cards",
                },
                {
                    "type": "answer",
                    "text": "Richtig: C einen Termin auf später legen",
                    "image_prompt": "Classroom",
                },
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )


def settings(tmp_path: Path) -> Settings:
    return Settings(environment="test", media_root=tmp_path)


def video(tmp_path: Path) -> Path:
    path = tmp_path / "short.mp4"
    path.write_bytes(b"video")
    return path


def audio(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "audio" / "42" / "voiceover.mp3"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")
    return path, LocalStorage().checksum(path)


def image_paths(tmp_path: Path) -> list[Path]:
    return [tmp_path / f"frame_{index}.png" for index in range(1, 4)]
