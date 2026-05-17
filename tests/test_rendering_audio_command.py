from pathlib import Path

import pytest

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.ffmpeg_renderer import build_ffmpeg_command
from shorts_factory.rendering.qa_probe import (
    QAError,
    VideoProbe,
    VideoQAService,
    parse_ffprobe_output,
)
from shorts_factory.rendering.render_plan import build_render_plan
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


class StaticProbe:
    def probe(self, video_path: str) -> VideoProbe:
        return VideoProbe(
            path=video_path,
            width=1080,
            height=1920,
            duration_sec=15.5,
            has_audio=True,
        )


def test_ffmpeg_command_pads_audio_to_render_duration(tmp_path: Path) -> None:
    app_settings = Settings(environment="test", media_root=tmp_path)
    plan = render_plan(tmp_path, app_settings)

    command = build_ffmpeg_command(app_settings, plan)
    filter_graph = command[command.index("-filter_complex") + 1]

    assert "-shortest" not in command
    assert "-loop" not in command
    assert command.count("-t") == 1
    assert "[aout]" in command
    assert "textfile='" in filter_graph
    assert "\\n" not in filter_graph
    assert "atrim=0:15.5" in filter_graph
    assert "apad=whole_dur=15.5[aout]" in filter_graph
    assert "between(t,0.0,1.0)" not in filter_graph


def test_parse_ffprobe_output_detects_audio_and_dimensions() -> None:
    output = """
    {
      "streams": [
        {"codec_type": "video", "width": 1080, "height": 1920},
        {"codec_type": "audio"}
      ],
      "format": {"duration": "15.5"}
    }
    """

    probe = parse_ffprobe_output("video.mp4", output)

    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.has_audio
    assert probe.duration_sec == 15.5


def test_qa_rejects_missing_video_file(tmp_path: Path) -> None:
    qa = VideoQAService(StaticProbe())

    with pytest.raises(QAError):
        qa.validate(
            video_path=str(tmp_path / "missing.mp4"),
            quiz=quiz(),
            render_plan=render_plan(tmp_path),
        )


def render_plan(tmp_path: Path, app_settings: Settings | None = None):
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"audio")
    return build_render_plan(
        settings=app_settings or Settings(environment="test", media_root=tmp_path),
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
            "id": "quiz-1",
            "question": "Was bedeutet 'Haus'?",
            "options": [{"label": "A", "text": "house"}, {"label": "B", "text": "car"}],
            "correct_answer": "A",
            "explanation": "Haus bedeutet house.",
            "level": "A1",
            "topic": "Vocabulary",
            "status": "approved",
        }
    )


def script() -> GeneratedScript:
    return GeneratedScript.model_validate(
        {
            "frames": [
                {"type": "question", "text": "Was bedeutet 'Haus'?", "image_prompt": "Classroom"},
                {"type": "options", "text": "A house\nB car", "image_prompt": "Quiz lesson"},
                {"type": "answer", "text": "Richtig ist: A house", "image_prompt": "Student"},
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )
