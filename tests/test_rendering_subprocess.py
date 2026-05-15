from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.ffmpeg_renderer import FFmpegRenderer, RenderError
from shorts_factory.rendering.qa_probe import FFprobeVideoProbe, QAError, parse_ffprobe_output
from shorts_factory.rendering.render_plan import RenderPlan, build_render_plan
from shorts_factory.settings import Settings


def test_ffmpeg_renderer_returns_output_path(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(command, capture_output, check, text):
        calls.append(command)
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("shorts_factory.rendering.ffmpeg_renderer.subprocess.run", fake_run)
    output_path = FFmpegRenderer(Settings(environment="test")).render(render_plan(tmp_path))

    assert output_path.endswith("short.mp4")
    assert calls[0][0] == "ffmpeg"


def test_ffmpeg_renderer_raises_render_error(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, capture_output, check, text):
        return SimpleNamespace(returncode=1, stderr="bad render")

    monkeypatch.setattr("shorts_factory.rendering.ffmpeg_renderer.subprocess.run", fake_run)

    with pytest.raises(RenderError, match="bad render"):
        FFmpegRenderer(Settings(environment="test")).render(render_plan(tmp_path))


def test_ffprobe_video_probe_parses_subprocess_output(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text):
        return SimpleNamespace(returncode=0, stdout=ffprobe_output(), stderr="")

    monkeypatch.setattr("shorts_factory.rendering.qa_probe.subprocess.run", fake_run)

    probe = FFprobeVideoProbe(Settings(environment="test")).probe("short.mp4")

    assert probe.width == 1080
    assert probe.has_audio


def test_ffprobe_video_probe_raises_on_subprocess_failure(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text):
        return SimpleNamespace(returncode=1, stdout="", stderr="ffprobe failed hard")

    monkeypatch.setattr("shorts_factory.rendering.qa_probe.subprocess.run", fake_run)

    with pytest.raises(QAError, match="failed hard"):
        FFprobeVideoProbe(Settings(environment="test")).probe("short.mp4")


@pytest.mark.parametrize(
    ("output", "message"),
    [
        ('{"streams": [], "format": {"duration": "18.0"}}', "Video stream is missing"),
        ('{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}]}', "duration"),
    ],
)
def test_parse_ffprobe_output_rejects_missing_required_fields(output: str, message: str) -> None:
    with pytest.raises(QAError, match=message):
        parse_ffprobe_output("short.mp4", output)


def render_plan(tmp_path: Path) -> RenderPlan:
    return build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=1,
        quiz=quiz(),
        script=script(),
        image_paths=[tmp_path / f"{index}.png" for index in range(1, 7)],
        audio_path=tmp_path / "voice.mp3",
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
            "hook": "Kannst du das lösen?",
            "voiceover": "Was bedeutet 'Haus'? Richtig ist A, house.",
            "frames": [
                {"type": "hook", "text": "Hook", "image_prompt": "Curious student"},
                {"type": "question", "text": "Was bedeutet 'Haus'?", "image_prompt": "Classroom"},
                {"type": "options", "text": "A house\nB car", "image_prompt": "Quiz lesson"},
                {"type": "pause", "text": "3\n2\n1", "image_prompt": "Thinking student"},
                {"type": "answer", "text": "Richtig ist: A house", "image_prompt": "Student"},
                {"type": "cta", "text": "Folge uns!", "image_prompt": "Learning atmosphere"},
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )


def ffprobe_output() -> str:
    return """
    {
      "streams": [
        {"codec_type": "video", "width": 1080, "height": 1920},
        {"codec_type": "audio"}
      ],
      "format": {"duration": "18.0"}
    }
    """
