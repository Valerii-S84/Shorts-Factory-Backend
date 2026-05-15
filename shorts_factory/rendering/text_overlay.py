from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from textwrap import wrap

from pydantic import BaseModel, Field, field_validator

DEFAULT_MAX_LINE_CHARS = 28


class OverlayKind(StrEnum):
    HOOK = "hook"
    QUESTION = "question"
    OPTIONS = "options"
    COUNTDOWN = "countdown"
    ANSWER = "answer"
    CTA = "cta"


@dataclass(frozen=True)
class OverlayTemplate:
    kind: OverlayKind
    x: str
    y: str
    max_font_size: int
    min_font_size: int
    max_line_chars: int
    max_lines: int
    font_color: str = "white"
    box_color: str = "black@0.65"
    box_borderw: int = 24
    line_spacing: int = 8


OVERLAY_TEMPLATES = {
    OverlayKind.HOOK: OverlayTemplate(
        kind=OverlayKind.HOOK,
        x="(w-text_w)/2",
        y="h*0.14",
        max_font_size=82,
        min_font_size=58,
        max_line_chars=24,
        max_lines=3,
        box_color="black@0.72",
        box_borderw=28,
    ),
    OverlayKind.QUESTION: OverlayTemplate(
        kind=OverlayKind.QUESTION,
        x="(w-text_w)/2",
        y="h*0.20",
        max_font_size=68,
        min_font_size=48,
        max_line_chars=28,
        max_lines=4,
        box_color="black@0.68",
    ),
    OverlayKind.OPTIONS: OverlayTemplate(
        kind=OverlayKind.OPTIONS,
        x="(w-text_w)/2",
        y="h*0.48",
        max_font_size=60,
        min_font_size=42,
        max_line_chars=30,
        max_lines=8,
        box_color="black@0.70",
        line_spacing=12,
    ),
    OverlayKind.COUNTDOWN: OverlayTemplate(
        kind=OverlayKind.COUNTDOWN,
        x="(w-text_w)/2",
        y="(h-text_h)/2",
        max_font_size=118,
        min_font_size=96,
        max_line_chars=3,
        max_lines=3,
        box_color="black@0.50",
        box_borderw=34,
    ),
    OverlayKind.ANSWER: OverlayTemplate(
        kind=OverlayKind.ANSWER,
        x="(w-text_w)/2",
        y="h*0.56",
        max_font_size=66,
        min_font_size=44,
        max_line_chars=30,
        max_lines=5,
        box_color="0x166534@0.78",
        box_borderw=28,
        line_spacing=10,
    ),
    OverlayKind.CTA: OverlayTemplate(
        kind=OverlayKind.CTA,
        x="(w-text_w)/2",
        y="h*0.72",
        max_font_size=60,
        min_font_size=44,
        max_line_chars=28,
        max_lines=3,
        box_color="0x1d4ed8@0.76",
        box_borderw=24,
    ),
}


class TextOverlay(BaseModel):
    text: str
    kind: OverlayKind = OverlayKind.QUESTION
    x: str = "(w-text_w)/2"
    y: str = "h*0.68"
    font_size: int = Field(default=64, ge=24, le=120)
    max_line_chars: int = Field(default=DEFAULT_MAX_LINE_CHARS, ge=1, le=40)
    max_lines: int = Field(default=6, ge=1, le=12)
    font_color: str = "white"
    box_color: str = "black@0.65"
    box_borderw: int = Field(default=24, ge=0, le=80)
    line_spacing: int = Field(default=8, ge=0, le=40)
    countdown_values: tuple[str, ...] = ()
    countdown_interval_sec: float = Field(default=1.0, gt=0, le=5.0)

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Text overlay must not be empty.")
        return stripped

    @property
    def wrapped_lines(self) -> list[str]:
        return wrapped_overlay_lines(self.text, self.max_line_chars)

    @property
    def has_overflow_risk(self) -> bool:
        lines = self.wrapped_lines
        return len(lines) > self.max_lines or any(len(line) > self.max_line_chars for line in lines)


def build_text_overlay(kind: OverlayKind, text: str) -> TextOverlay:
    template = OVERLAY_TEMPLATES[kind]
    return TextOverlay(
        text=text,
        kind=template.kind,
        x=template.x,
        y=template.y,
        font_size=_dynamic_font_size(text, template),
        max_line_chars=template.max_line_chars,
        max_lines=template.max_lines,
        font_color=template.font_color,
        box_color=template.box_color,
        box_borderw=template.box_borderw,
        line_spacing=template.line_spacing,
        countdown_values=("3", "2", "1") if kind == OverlayKind.COUNTDOWN else (),
    )


def drawtext_filter(overlay: TextOverlay) -> str:
    return _drawtext_filter(overlay)


def drawtext_filters(overlay: TextOverlay) -> list[str]:
    if overlay.kind != OverlayKind.COUNTDOWN or not overlay.countdown_values:
        return [_drawtext_filter(overlay)]

    filters = []
    for index, value in enumerate(overlay.countdown_values):
        countdown_overlay = overlay.model_copy(update={"text": value})
        start_sec = index * overlay.countdown_interval_sec
        end_sec = start_sec + overlay.countdown_interval_sec
        enable = f"between(t,{start_sec},{end_sec})"
        filters.append(_drawtext_filter(countdown_overlay, enable=enable))
    return filters


def _drawtext_filter(overlay: TextOverlay, *, enable: str | None = None) -> str:
    escaped = escape_drawtext_text(wrap_overlay_text(overlay.text, overlay.max_line_chars))
    enable_fragment = f":enable='{enable}'" if enable is not None else ""
    return (
        "drawtext="
        f"text='{escaped}':"
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


def wrap_overlay_text(text: str, max_line_chars: int = DEFAULT_MAX_LINE_CHARS) -> str:
    return "\n".join(wrapped_overlay_lines(text, max_line_chars))


def wrapped_overlay_lines(text: str, max_line_chars: int = DEFAULT_MAX_LINE_CHARS) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lines.extend(
            wrap(
                line,
                width=max_line_chars,
                break_long_words=True,
                break_on_hyphens=False,
            )
        )
    return lines


def escape_drawtext_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace("\n", "\\n")
    )


def _dynamic_font_size(text: str, template: OverlayTemplate) -> int:
    lines = wrapped_overlay_lines(text, template.max_line_chars)
    longest_line = max((len(line) for line in lines), default=0)
    line_pressure = max(0, len(lines) - 2) * 6
    length_pressure = max(0, longest_line - int(template.max_line_chars * 0.75)) * 2
    font_size = template.max_font_size - line_pressure - length_pressure
    return max(template.min_font_size, min(template.max_font_size, font_size))
