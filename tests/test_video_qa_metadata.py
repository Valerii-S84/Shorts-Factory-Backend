from pathlib import Path

import pytest

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.qa_probe import QAError, VideoProbe, VideoQAService
from shorts_factory.rendering.render_plan import build_render_plan
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


def test_render_plan_contains_creative_metadata(tmp_path: Path) -> None:
    plan = render_plan(tmp_path)

    assert plan.creative_metadata.video_id == "job-1"
    assert plan.creative_metadata.frame_sequence == ["question", "options", "answer"]
    assert plan.creative_metadata.answer_reveal_at_sec == 10.0
    assert not plan.creative_metadata.has_countdown
    assert plan.creative_metadata.voice_model == "gpt-4o-mini-tts"
    assert plan.creative_metadata.voice_id == "cedar"
    assert plan.creative_metadata.voice_speed == 0.8
    assert plan.creative_metadata.narration_parts_count == 3
    assert plan.creative_metadata.narration_contains_all_options


@pytest.mark.parametrize(
    ("probe", "message"),
    [
        (VideoProbe(path="", width=720, height=1280, duration_sec=18, has_audio=True), "1080x1920"),
        (VideoProbe(path="", width=1080, height=1920, duration_sec=21, has_audio=True), "15.5"),
        (VideoProbe(path="", width=1080, height=1920, duration_sec=15.5, has_audio=False), "audio"),
    ],
)
def test_video_qa_service_rejects_invalid_probe(
    tmp_path: Path, probe: VideoProbe, message: str
) -> None:
    with pytest.raises(QAError, match=message):
        VideoQAService(StaticProbe(probe)).validate(
            video_path=str(video(tmp_path)),
            quiz=quiz(),
            render_plan=render_plan(tmp_path),
        )


class StaticProbe:
    def __init__(self, probe: VideoProbe) -> None:
        self._probe = probe

    def probe(self, video_path: str) -> VideoProbe:
        return self._probe.model_copy(update={"path": video_path})


def render_plan(tmp_path: Path):
    audio_path = tmp_path / "voice.mp3"
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


def video(tmp_path: Path) -> Path:
    path = tmp_path / "short.mp4"
    path.write_bytes(b"video")
    return path
