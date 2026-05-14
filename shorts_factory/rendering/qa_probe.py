from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.render_plan import RenderPlan
from shorts_factory.settings import Settings


class QAError(RuntimeError):
    pass


class VideoProbe(BaseModel):
    path: str
    width: int
    height: int
    duration_sec: float
    has_audio: bool


class QAResult(BaseModel):
    passed: bool
    probe: VideoProbe


class FFprobeVideoProbe:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def probe(self, video_path: str) -> VideoProbe:
        command = [
            self._settings.ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            video_path,
        ]
        result = subprocess.run(command, capture_output=True, check=False, text=True)
        if result.returncode != 0:
            raise QAError(result.stderr.strip() or "ffprobe failed.")
        return parse_ffprobe_output(video_path, result.stdout)


def parse_ffprobe_output(video_path: str, output: str) -> VideoProbe:
    payload = json.loads(output)
    streams = payload.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video_stream is None:
        raise QAError("Video stream is missing.")

    duration = payload.get("format", {}).get("duration") or video_stream.get("duration")
    if duration is None:
        raise QAError("Video duration is missing.")

    return VideoProbe(
        path=video_path,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        duration_sec=float(duration),
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
    )


class VideoQAService:
    def __init__(self, probe: FFprobeVideoProbe) -> None:
        self._probe = probe

    def validate(
        self,
        *,
        video_path: str,
        quiz: Quiz,
        render_plan: RenderPlan,
    ) -> QAResult:
        _validate_static_requirements(video_path, quiz, render_plan)
        probe = self._probe.probe(video_path)
        _validate_probe(probe)
        return QAResult(passed=True, probe=probe)


def _validate_static_requirements(video_path: str, quiz: Quiz, render_plan: RenderPlan) -> None:
    path = Path(video_path)
    if not path.exists():
        raise QAError("Video file is missing.")
    if path.suffix.lower() != ".mp4":
        raise QAError("Video file must be MP4.")
    if not render_plan.has_text_overlays:
        raise QAError("Render plan does not contain text overlays.")
    if render_plan.correct_option_label != quiz.correct_option_label:
        raise QAError("Correct answer label does not match Quiz Bank.")
    if render_plan.correct_answer_text != quiz.correct_option.text:
        raise QAError("Correct answer text does not match Quiz Bank.")
    if not render_plan.telegram_caption:
        raise QAError("Telegram caption is missing.")
    if not render_plan.youtube_title:
        raise QAError("YouTube title is missing.")


def _validate_probe(probe: VideoProbe) -> None:
    if probe.width != 1080 or probe.height != 1920:
        raise QAError("Video must be 1080x1920.")
    if probe.duration_sec > 20:
        raise QAError("Video duration must be 20 seconds or less.")
    if not probe.has_audio:
        raise QAError("Video audio stream is missing.")
