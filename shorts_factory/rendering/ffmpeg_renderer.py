from __future__ import annotations

import subprocess
from pathlib import Path

from shorts_factory.rendering.render_plan import RenderPlan
from shorts_factory.rendering.text_overlay import drawtext_filters
from shorts_factory.settings import Settings


class RenderError(RuntimeError):
    pass


class FFmpegRenderer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def render(self, plan: RenderPlan) -> str:
        Path(plan.output_path).parent.mkdir(parents=True, exist_ok=True)
        command = build_ffmpeg_command(self._settings, plan)
        result = subprocess.run(command, capture_output=True, check=False, text=True)
        if result.returncode != 0:
            raise RenderError(result.stderr.strip() or "FFmpeg render failed.")
        return plan.output_path


def build_ffmpeg_command(settings: Settings, plan: RenderPlan) -> list[str]:
    command = [settings.ffmpeg_path, "-y"]
    for frame in plan.frames:
        command.extend(["-loop", "1", "-t", str(frame.duration_sec), "-i", frame.image_path])
    command.extend(["-i", plan.audio_path])

    filters = []
    concat_inputs = []
    for index, frame in enumerate(plan.frames):
        frame_count = max(1, int(frame.duration_sec * plan.fps))
        overlay_filters = ",".join(drawtext_filters(frame.text_overlay))
        filters.append(
            f"[{index}:v]"
            f"scale={plan.width}:{plan.height}:force_original_aspect_ratio=increase,"
            f"crop={plan.width}:{plan.height},"
            f"zoompan=z='min(zoom+0.0015,1.08)':d={frame_count}:"
            f"s={plan.width}x{plan.height}:fps={plan.fps},"
            f"{overlay_filters},"
            f"setpts=PTS-STARTPTS[v{index}]"
        )
        concat_inputs.append(f"[v{index}]")

    filters.append(f"{''.join(concat_inputs)}concat=n={len(plan.frames)}:v=1:a=0[vout]")
    audio_input = len(plan.frames)
    filters.append(
        f"[{audio_input}:a]"
        f"atrim=0:{plan.duration_sec},"
        "asetpts=PTS-STARTPTS,"
        f"apad=whole_dur={plan.duration_sec}[aout]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-t",
            str(plan.duration_sec),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            plan.output_path,
        ]
    )
    return command
