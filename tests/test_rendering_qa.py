from pathlib import Path

import pytest

from shorts_factory.generation.schemas import FrameType, GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.ffmpeg_renderer import build_ffmpeg_command
from shorts_factory.rendering.qa_probe import (
    QAError,
    VideoProbe,
    VideoQAService,
    parse_ffprobe_output,
)
from shorts_factory.rendering.render_plan import build_render_plan
from shorts_factory.rendering.text_overlay import wrapped_overlay_lines
from shorts_factory.settings import Settings


class StaticProbe:
    def __init__(self, probe: VideoProbe) -> None:
        self._probe = probe

    def probe(self, video_path: str) -> VideoProbe:
        return self._probe.model_copy(update={"path": video_path})


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


def a2_long_explanation_quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-a2-overflow",
            "question": "Was bedeutet 'den Termin verschieben'?",
            "options": [
                {"label": "A", "text": "pünktlich ankommen"},
                {"label": "B", "text": "den Termin verschieben"},
            ],
            "correct_answer": "B",
            "explanation": (
                "Man sagt den Termin verschieben, wenn ein Treffen auf einen anderen "
                "Zeitpunkt gelegt wird."
            ),
            "level": "A2",
            "topic": "Alltag",
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


def test_render_plan_keeps_quiz_answer_and_text_overlays(tmp_path: Path) -> None:
    settings = Settings(environment="test", media_root=tmp_path)
    image_paths = [tmp_path / f"{index}.png" for index in range(1, 7)]
    audio_path = tmp_path / "voice.mp3"

    plan = build_render_plan(
        settings=settings,
        job_id=1,
        quiz=quiz(),
        script=script(),
        image_paths=image_paths,
        audio_path=audio_path,
    )

    assert plan.correct_option_label == "A"
    assert plan.correct_answer_text == "house"
    assert plan.has_text_overlays
    assert plan.duration_sec == 17.5
    assert plan.frames[2].text_overlay.text == "A  house\nB  car"
    assert "Haus bedeutet house." in plan.frames[4].text_overlay.text
    assert plan.answer_reveal_at_sec == 12.0
    assert plan.creative_metadata.template_id == "speed"
    assert plan.output_path.endswith("videos/1/short.mp4")


def test_render_plan_trims_long_answer_explanation_to_fit_overlay(tmp_path: Path) -> None:
    source_quiz = a2_long_explanation_quiz()
    original_explanation = source_quiz.explanation

    plan = build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=3,
        quiz=source_quiz,
        script=script(),
        image_paths=[tmp_path / f"{index}.png" for index in range(1, 7)],
        audio_path=tmp_path / "voice.mp3",
    )

    answer_frame = next(frame for frame in plan.frames if frame.type == FrameType.ANSWER)

    assert "Richtig: B den Termin verschieben" in answer_frame.text_overlay.text
    assert plan.correct_answer_text == "den Termin verschieben"
    assert source_quiz.explanation == original_explanation
    assert plan.explanation_text == "Man sagt den Termin verschieben..."
    assert plan.explanation_text != original_explanation
    assert (
        len(wrapped_overlay_lines(plan.explanation_text, answer_frame.text_overlay.max_line_chars))
        <= 2
    )
    assert len(answer_frame.text_overlay.wrapped_lines) <= answer_frame.text_overlay.max_lines
    assert answer_frame.text_overlay.max_lines == 5
    assert not answer_frame.text_overlay.has_overflow_risk


def test_qa_accepts_job_three_a2_long_answer_fixture_after_display_trim(tmp_path: Path) -> None:
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    source_quiz = a2_long_explanation_quiz()
    plan = build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=3,
        quiz=source_quiz,
        script=script(),
        image_paths=[tmp_path / f"{index}.png" for index in range(1, 7)],
        audio_path=tmp_path / "voice.mp3",
    )
    qa = VideoQAService(
        StaticProbe(VideoProbe(path="", width=1080, height=1920, duration_sec=18, has_audio=True))
    )

    result = qa.validate(video_path=str(video_path), quiz=source_quiz, render_plan=plan)

    assert result.passed


def test_ffmpeg_command_pads_audio_to_render_duration(tmp_path: Path) -> None:
    settings = Settings(environment="test", media_root=tmp_path)
    plan = build_render_plan(
        settings=settings,
        job_id=1,
        quiz=quiz(),
        script=script(),
        image_paths=[
            tmp_path / "1.png",
            tmp_path / "2.png",
            tmp_path / "3.png",
            tmp_path / "4.png",
            tmp_path / "5.png",
            tmp_path / "6.png",
        ],
        audio_path=tmp_path / "voice.mp3",
    )

    command = build_ffmpeg_command(settings, plan)
    filter_graph = command[command.index("-filter_complex") + 1]

    assert "-shortest" not in command
    assert "[aout]" in command
    assert "apad=whole_dur=17.5[aout]" in filter_graph
    assert "between(t\\,0.0\\,1.0)" not in filter_graph
    assert "between(t,0.0,1.0)" in filter_graph


def test_parse_ffprobe_output_detects_audio_and_dimensions() -> None:
    output = """
    {
      "streams": [
        {"codec_type": "video", "width": 1080, "height": 1920},
        {"codec_type": "audio"}
      ],
      "format": {"duration": "18.0"}
    }
    """

    probe = parse_ffprobe_output("video.mp4", output)

    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.has_audio


def test_qa_rejects_missing_video_file(tmp_path: Path) -> None:
    settings = Settings(environment="test", media_root=tmp_path)
    plan = build_render_plan(
        settings=settings,
        job_id=1,
        quiz=quiz(),
        script=script(),
        image_paths=[
            tmp_path / "1.png",
            tmp_path / "2.png",
            tmp_path / "3.png",
            tmp_path / "4.png",
            tmp_path / "5.png",
            tmp_path / "6.png",
        ],
        audio_path=tmp_path / "voice.mp3",
    )
    qa = VideoQAService(
        StaticProbe(VideoProbe(path="", width=1080, height=1920, duration_sec=18, has_audio=True))
    )

    with pytest.raises(QAError):
        qa.validate(video_path=str(tmp_path / "missing.mp4"), quiz=quiz(), render_plan=plan)
