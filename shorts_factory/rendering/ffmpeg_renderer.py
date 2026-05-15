from __future__ import annotations

import subprocess
from pathlib import Path

from shorts_factory.rendering.render_plan import RenderPlan
from shorts_factory.rendering.text_overlay import OverlayKind, TextOverlay, wrap_overlay_text
from shorts_factory.settings import Settings


class RenderError(RuntimeError):
    pass


class FFmpegRenderer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def render(self, plan: RenderPlan) -> str:
        Path(plan.output_path).parent.mkdir(parents=True, exist_ok=True)
        _write_drawtext_files(plan)
        command = build_ffmpeg_command(self._settings, plan)
        result = subprocess.run(command, capture_output=True, check=False, text=True)
        if result.returncode != 0:
            raise RenderError(result.stderr.strip() or "FFmpeg render failed.")
        return plan.output_path


def build_ffmpeg_command(settings: Settings, plan: RenderPlan) -> list[str]:
    command = [settings.ffmpeg_path, "-y"]
    for frame in plan.frames:
        command.extend(["-i", frame.image_path])
    command.extend(["-i", plan.audio_path])

    filters = []
    concat_inputs = []
    for index, frame in enumerate(plan.frames):
        frame_count = max(1, int(frame.duration_sec * plan.fps))
        overlay_filters = ",".join(
            _drawtext_filters(frame.text_overlay, _drawtext_file(plan, index))
        )
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


def _write_drawtext_files(plan: RenderPlan) -> None:
    for index, frame in enumerate(plan.frames):
        text_file = _drawtext_file(plan, index)
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text(
            wrap_overlay_text(frame.text_overlay.text, frame.text_overlay.max_line_chars),
            encoding="utf-8",
        )
        if frame.text_overlay.kind == OverlayKind.COUNTDOWN:
            for countdown_index, value in enumerate(frame.text_overlay.countdown_values):
                text_file.with_name(f"{text_file.stem}_{countdown_index}.txt").write_text(
                    value,
                    encoding="utf-8",
                )


def _drawtext_file(plan: RenderPlan, index: int) -> Path:
    return Path(plan.output_path).with_suffix("").parent / "drawtext" / f"frame_{index:02d}.txt"


def _drawtext_filters(overlay: TextOverlay, text_file: Path) -> list[str]:
    if overlay.kind != OverlayKind.COUNTDOWN or not overlay.countdown_values:
        return [_drawtext_filter(overlay, text_file=text_file)]

    filters = []
    for index, _value in enumerate(overlay.countdown_values):
        countdown_text_file = text_file.with_name(f"{text_file.stem}_{index}.txt")
        start_sec = index * overlay.countdown_interval_sec
        end_sec = start_sec + overlay.countdown_interval_sec
        enable = f"between(t,{start_sec},{end_sec})"
        filters.append(_drawtext_filter(overlay, text_file=countdown_text_file, enable=enable))
    return filters


def _drawtext_filter(
    overlay: TextOverlay,
    *,
    text_file: Path,
    enable: str | None = None,
) -> str:
    enable_fragment = f":enable='{enable}'" if enable is not None else ""
    return (
        "drawtext="
        f"textfile='{_escape_filter_path(text_file)}':"
        f"fontcolor={overlay.font_color}:"
        f"fontsize={overlay.font_size}:"
        f"line_spacing={overlay.line_spacing}:"
        "box=1:"
        f"boxcolor={overlay.box_color}:"
        f"boxborderw={overlay.box_borderw}:"
        f"x={overlay.x}:"
        f"y={overlay.y}"
        f"{enable_fragment}"
    )


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
