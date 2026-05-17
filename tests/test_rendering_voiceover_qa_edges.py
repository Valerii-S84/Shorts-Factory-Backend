from __future__ import annotations

from pathlib import Path

import pytest

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.qa_probe import (
    QAError,
    VideoProbe,
    VideoQAService,
    parse_ffprobe_output,
)
from shorts_factory.rendering.render_plan import RenderPlan, build_render_plan
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


def test_parse_ffprobe_output_ignores_invalid_audio_duration() -> None:
    probe = parse_ffprobe_output(
        "short.mp4",
        """
        {
          "streams": [
            {"codec_type": "video", "width": 1080, "height": 1920},
            {"codec_type": "audio", "duration": "n/a"}
          ],
          "format": {"duration": "15.5"}
        }
        """,
    )

    assert probe.has_audio
    assert probe.audio_duration_sec is None


def test_video_qa_rejects_audio_stream_longer_than_video(tmp_path: Path) -> None:
    with pytest.raises(QAError, match="audio stream is longer"):
        qa(tmp_path, probe=valid_probe(audio_duration_sec=20)).validate(
            video_path=str(video(tmp_path)), quiz=quiz(), render_plan=render_plan(tmp_path)
        )


@pytest.mark.parametrize(
    ("plan_update", "message"),
    [
        ({"has_voiceover": False}, "voiceover flag"),
        ({"voice_model": "wrong-model"}, "Voice model"),
        ({"voice_id": "nova"}, "Voice id"),
        ({"voice_speed": 1.0}, "Voice speed"),
        ({"narration_parts_count": 2}, "exactly 3 parts"),
        ({"narration_contains_question": False}, "missing the question"),
        ({"narration_contains_correct_answer": False}, "missing the correct answer"),
    ],
)
def test_video_qa_rejects_voiceover_metadata_errors(
    tmp_path: Path, plan_update: dict[str, object], message: str
) -> None:
    plan = render_plan(tmp_path).model_copy(update=plan_update)

    with pytest.raises(QAError, match=message):
        qa(tmp_path).validate(video_path=str(video(tmp_path)), quiz=quiz(), render_plan=plan)


def test_video_qa_rejects_unknown_template(tmp_path: Path) -> None:
    plan = render_plan(tmp_path).model_copy(update={"template_id": "unknown"})

    with pytest.raises(QAError, match="Unknown production template"):
        qa(tmp_path).validate(video_path=str(video(tmp_path)), quiz=quiz(), render_plan=plan)


def test_video_qa_rejects_audio_without_checksum(tmp_path: Path) -> None:
    plan = render_plan(tmp_path).model_copy(update={"audio_checksum": None})

    with pytest.raises(QAError, match="checksum"):
        qa(tmp_path).validate(video_path=str(video(tmp_path)), quiz=quiz(), render_plan=plan)


class StaticProbe:
    def __init__(self, probe: VideoProbe) -> None:
        self._probe = probe

    def probe(self, video_path: str) -> VideoProbe:
        return self._probe.model_copy(update={"path": video_path})


def qa(tmp_path: Path, probe: VideoProbe | None = None) -> VideoQAService:
    return VideoQAService(StaticProbe(probe or valid_probe()))


def valid_probe(*, audio_duration_sec: float | None = None) -> VideoProbe:
    return VideoProbe(
        path="",
        width=1080,
        height=1920,
        duration_sec=15.5,
        has_audio=True,
        audio_duration_sec=audio_duration_sec,
    )


def render_plan(tmp_path: Path) -> RenderPlan:
    audio_path = tmp_path / "voiceover.mp3"
    audio_path.write_bytes(b"audio")
    return build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=1,
        quiz=quiz(),
        script=script(),
        image_paths=[tmp_path / "1.png", tmp_path / "2.png", tmp_path / "3.png"],
        audio_path=audio_path,
        audio_checksum=LocalStorage().checksum(audio_path),
    )


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-qa-edge",
            "question": "Was passt?",
            "options": [{"label": "A", "text": "heute"}, {"label": "B", "text": "gestern"}],
            "correct_answer": "A",
            "explanation": "Heute passt.",
            "level": "A2",
            "topic": "Alltag",
            "status": "approved",
        }
    )


def script() -> GeneratedScript:
    return GeneratedScript.model_validate(
        {
            "frames": [
                {"type": "question", "text": "Was passt?", "image_prompt": "Student"},
                {"type": "options", "text": "A heute\nB gestern", "image_prompt": "Cards"},
                {"type": "answer", "text": "Richtig: A heute", "image_prompt": "Classroom"},
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )


def video(tmp_path: Path) -> Path:
    path = tmp_path / "short.mp4"
    path.write_bytes(b"video")
    return path
