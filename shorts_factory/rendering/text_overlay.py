from __future__ import annotations

from textwrap import wrap

from pydantic import BaseModel, Field, field_validator

DEFAULT_MAX_LINE_CHARS = 28


class TextOverlay(BaseModel):
    text: str
    x: str = "(w-text_w)/2"
    y: str = "h*0.68"
    font_size: int = Field(default=64, ge=24, le=120)
    max_line_chars: int = Field(default=DEFAULT_MAX_LINE_CHARS, ge=12, le=40)

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Text overlay must not be empty.")
        return stripped


def drawtext_filter(overlay: TextOverlay) -> str:
    escaped = escape_drawtext_text(wrap_overlay_text(overlay.text, overlay.max_line_chars))
    return (
        "drawtext="
        f"text='{escaped}':"
        "fontcolor=white:"
        f"fontsize={overlay.font_size}:"
        "box=1:"
        "boxcolor=black@0.65:"
        "boxborderw=24:"
        f"x={overlay.x}:"
        f"y={overlay.y}"
    )


def wrap_overlay_text(text: str, max_line_chars: int = DEFAULT_MAX_LINE_CHARS) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lines.extend(wrap(line, width=max_line_chars, break_long_words=False))
    return "\n".join(lines)


def escape_drawtext_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace("\n", "\\n")
    )
