from pathlib import Path

from shorts_factory.generation.schemas import FrameType, GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.qa_probe import VideoProbe, VideoQAService
from shorts_factory.rendering.render_plan import build_render_plan
from shorts_factory.rendering.text_overlay import wrapped_overlay_lines
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


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
            "options": [
                {"label": "A", "text": "house"},
                {"label": "B", "text": "car"},
                {"label": "C", "text": "tree"},
                {"label": "D", "text": "street"},
            ],
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
                {"label": "C", "text": "einen Termin absagen"},
                {"label": "D", "text": "zu spät kommen"},
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


def test_render_plan_keeps_quiz_answer_and_text_overlays(tmp_path: Path) -> None:
    settings = Settings(environment="test", media_root=tmp_path)
    image_paths = [tmp_path / f"{index}.png" for index in range(1, 4)]
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
    assert plan.duration_sec == 15.5
    assert plan.frames[1].text_overlay.text == "A  house\nB  car\nC  tree\nD  street"
    assert "Haus bedeutet house." in plan.frames[2].text_overlay.text
    assert plan.answer_reveal_at_sec == 10.0
    assert plan.creative_metadata.template_id == "speed"
    assert plan.output_path.endswith("videos/1/short.mp4")
    assert plan.narration_parts_count == 3
    assert plan.narration_contains_question
    assert plan.narration_contains_all_options
    assert plan.narration_contains_correct_answer


def test_render_plan_trims_long_answer_explanation_to_fit_overlay(tmp_path: Path) -> None:
    source_quiz = a2_long_explanation_quiz()
    original_explanation = source_quiz.explanation

    plan = build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=3,
        quiz=source_quiz,
        script=script(),
        image_paths=[tmp_path / f"{index}.png" for index in range(1, 4)],
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
    audio_path, audio_checksum = _audio(tmp_path)
    source_quiz = a2_long_explanation_quiz()
    plan = build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=3,
        quiz=source_quiz,
        script=script(),
        image_paths=[tmp_path / f"{index}.png" for index in range(1, 4)],
        audio_path=audio_path,
        audio_checksum=audio_checksum,
    )
    qa = VideoQAService(
        StaticProbe(VideoProbe(path="", width=1080, height=1920, duration_sec=15.5, has_audio=True))
    )

    result = qa.validate(video_path=str(video_path), quiz=source_quiz, render_plan=plan)

    assert result.passed


def _audio(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "voice.mp3"
    path.write_bytes(b"audio")
    return path, LocalStorage().checksum(path)
