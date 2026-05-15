from pathlib import Path

import pytest

from shorts_factory.generation.schemas import FrameType
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.qa_probe import QAError, VideoProbe, VideoQAService
from shorts_factory.rendering.render_plan import RenderFrame, RenderPlan
from shorts_factory.rendering.text_overlay import TextOverlay


def test_video_qa_service_accepts_valid_probe(tmp_path: Path) -> None:
    video_path = _video(tmp_path)
    result = VideoQAService(StaticProbe(valid_probe(video_path))).validate(
        video_path=str(video_path), quiz=quiz(), render_plan=render_plan(tmp_path)
    )

    assert result.passed


@pytest.mark.parametrize(
    ("plan_update", "message"),
    [
        ({"correct_option_label": "B"}, "label"),
        ({"correct_answer_text": "car"}, "text"),
        ({"telegram_caption": ""}, "Telegram caption"),
        ({"youtube_title": ""}, "YouTube title"),
    ],
)
def test_video_qa_service_rejects_static_plan_mismatches(
    tmp_path: Path, plan_update: dict[str, str], message: str
) -> None:
    video_path = _video(tmp_path)
    plan = render_plan(tmp_path).model_copy(update=plan_update)

    with pytest.raises(QAError, match=message):
        VideoQAService(StaticProbe(valid_probe(video_path))).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=plan
        )


def test_video_qa_service_rejects_non_mp4_file(tmp_path: Path) -> None:
    video_path = tmp_path / "short.mov"
    video_path.write_bytes(b"video")

    with pytest.raises(QAError, match="MP4"):
        VideoQAService(StaticProbe(valid_probe(video_path))).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=render_plan(tmp_path)
        )


def test_video_qa_service_rejects_missing_overlays(tmp_path: Path) -> None:
    video_path = _video(tmp_path)
    frame = (
        render_plan(tmp_path)
        .frames[0]
        .model_copy(update={"text_overlay": TextOverlay.model_construct(text="")})
    )
    plan = render_plan(tmp_path).model_copy(update={"frames": [frame]})

    with pytest.raises(QAError, match="text overlays"):
        VideoQAService(StaticProbe(valid_probe(video_path))).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=plan
        )


@pytest.mark.parametrize(
    ("probe", "message"),
    [
        (VideoProbe(path="", width=720, height=1280, duration_sec=18, has_audio=True), "1080x1920"),
        (VideoProbe(path="", width=1080, height=1920, duration_sec=21, has_audio=True), "20"),
        (VideoProbe(path="", width=1080, height=1920, duration_sec=18, has_audio=False), "audio"),
    ],
)
def test_video_qa_service_rejects_invalid_probe(
    tmp_path: Path, probe: VideoProbe, message: str
) -> None:
    video_path = _video(tmp_path)

    with pytest.raises(QAError, match=message):
        VideoQAService(StaticProbe(probe)).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=render_plan(tmp_path)
        )


class StaticProbe:
    def __init__(self, probe: VideoProbe) -> None:
        self._probe = probe

    def probe(self, video_path: str) -> VideoProbe:
        return self._probe.model_copy(update={"path": video_path})


def render_plan(tmp_path: Path) -> RenderPlan:
    return RenderPlan(
        job_id=1,
        quiz_id="quiz-1",
        duration_sec=18,
        audio_path=str(tmp_path / "voice.mp3"),
        output_path=str(tmp_path / "videos" / "short.mp4"),
        frames=[
            RenderFrame(
                type=FrameType.QUESTION,
                image_path=str(tmp_path / "image.png"),
                duration_sec=18,
                text_overlay=TextOverlay(text="Was bedeutet 'Haus'?"),
            )
        ],
        correct_option_label="A",
        correct_answer_text="house",
        telegram_caption="Deutsch Quiz",
        youtube_title="Deutsch Quiz",
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


def valid_probe(path: Path) -> VideoProbe:
    return VideoProbe(path=str(path), width=1080, height=1920, duration_sec=18, has_audio=True)


def _video(tmp_path: Path) -> Path:
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    return video_path
