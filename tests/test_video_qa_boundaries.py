from pathlib import Path

import pytest

from shorts_factory.generation.schemas import FrameType, GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.qa_probe import QAError, VideoProbe, VideoQAService
from shorts_factory.rendering.render_plan import RenderPlan, build_render_plan
from shorts_factory.rendering.text_overlay import TextOverlay
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


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
    ("frame_type", "message"),
    [
        (FrameType.QUESTION, "question"),
        (FrameType.OPTIONS, "options"),
        (FrameType.ANSWER, "answer"),
    ],
)
def test_video_qa_service_rejects_missing_required_segments(
    tmp_path: Path, frame_type: FrameType, message: str
) -> None:
    video_path = _video(tmp_path)
    plan = render_plan(tmp_path)
    plan = plan.model_copy(
        update={"frames": [frame for frame in plan.frames if frame.type != frame_type]}
    )

    with pytest.raises(QAError, match=message):
        VideoQAService(StaticProbe(valid_probe(video_path))).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=plan
        )


def test_video_qa_service_rejects_wrong_answer_reveal_timing(tmp_path: Path) -> None:
    video_path = _video(tmp_path)
    plan = _update_frame(render_plan(tmp_path), FrameType.ANSWER, {"starts_at_sec": 13.0})

    with pytest.raises(QAError, match="Answer reveal"):
        VideoQAService(StaticProbe(valid_probe(video_path))).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=plan
        )


def test_video_qa_service_rejects_missing_explanation(tmp_path: Path) -> None:
    video_path = _video(tmp_path)
    plan = render_plan(tmp_path).model_copy(update={"explanation_text": ""})

    with pytest.raises(QAError, match="explanation"):
        VideoQAService(StaticProbe(valid_probe(video_path))).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=plan
        )


def test_video_qa_service_rejects_answer_reveal_before_answer_segment(tmp_path: Path) -> None:
    video_path = _video(tmp_path)
    plan = render_plan(tmp_path)
    options_frame = next(frame for frame in plan.frames if frame.type == FrameType.OPTIONS)
    leaking_overlay = options_frame.text_overlay.model_copy(
        update={"text": f"{options_frame.text_overlay.text}\n{plan.answer_reveal_text}"}
    )
    plan = _update_frame(plan, FrameType.OPTIONS, {"text_overlay": leaking_overlay})

    with pytest.raises(QAError, match="before the answer"):
        VideoQAService(StaticProbe(valid_probe(video_path))).validate(
            video_path=str(video_path), quiz=quiz(), render_plan=plan
        )


class StaticProbe:
    def __init__(self, probe: VideoProbe) -> None:
        self._probe = probe

    def probe(self, video_path: str) -> VideoProbe:
        return self._probe.model_copy(update={"path": video_path})


def render_plan(tmp_path: Path) -> RenderPlan:
    audio_path, audio_checksum = _audio(tmp_path)
    return build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=1,
        quiz=quiz(),
        script=script(),
        image_paths=[tmp_path / f"{index}.png" for index in range(1, 4)],
        audio_path=audio_path,
        audio_checksum=audio_checksum,
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


def valid_probe(path: Path) -> VideoProbe:
    return VideoProbe(path=str(path), width=1080, height=1920, duration_sec=15.5, has_audio=True)


def _video(tmp_path: Path) -> Path:
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    return video_path


def _audio(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "voice.mp3"
    path.write_bytes(b"audio")
    return path, LocalStorage().checksum(path)


def _update_frame(plan: RenderPlan, frame_type: FrameType, update: dict[str, object]) -> RenderPlan:
    frames = [
        frame.model_copy(update=update) if frame.type == frame_type else frame
        for frame in plan.frames
    ]
    return plan.model_copy(update={"frames": frames})
