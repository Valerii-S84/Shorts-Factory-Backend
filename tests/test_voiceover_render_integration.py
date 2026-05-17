from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.ffmpeg_renderer import FFmpegRenderer
from shorts_factory.rendering.qa_probe import FFprobeVideoProbe, VideoQAService
from shorts_factory.rendering.render_plan import build_render_plan
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required for render integration QA",
)
def test_rendered_video_contains_audio_stream_and_15_5_second_duration(tmp_path: Path) -> None:
    plan = render_plan_with_media(tmp_path)

    video_path = FFmpegRenderer(settings(tmp_path)).render(plan)
    result = VideoQAService(FFprobeVideoProbe(settings(tmp_path))).validate(
        video_path=video_path,
        quiz=quiz(),
        render_plan=plan,
    )

    assert result.probe.has_audio
    assert 15.4 <= result.probe.duration_sec <= 15.7


def render_plan_with_media(tmp_path: Path):
    images = write_fixture_images(tmp_path)
    audio_path = write_fixture_audio(tmp_path)
    return build_render_plan(
        settings=settings(tmp_path),
        job_id=42,
        quiz=quiz(),
        script=script(),
        image_paths=images,
        audio_path=audio_path,
        audio_checksum=LocalStorage().checksum(audio_path),
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


def write_fixture_images(tmp_path: Path) -> list[Path]:
    paths = [tmp_path / f"frame_{index}.png" for index in range(1, 4)]
    for path, color in zip(paths, ("0x1f2937", "0x0f766e", "0x7c2d12"), strict=True):
        run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=1080x1920:d=1",
                "-frames:v",
                "1",
                "-update",
                "1",
                str(path),
            ]
        )
    return paths


def write_fixture_audio(tmp_path: Path) -> Path:
    path = tmp_path / "audio" / "42" / "voiceover.mp3"
    path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=1",
            "-filter:a",
            "volume=0.04",
            "-q:a",
            "9",
            str(path),
        ]
    )
    return path


def run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, check=False, text=True, timeout=90)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
