import pytest
from pydantic import ValidationError

from shorts_factory.rendering.text_overlay import (
    TextOverlay,
    drawtext_filter,
    escape_drawtext_text,
    wrap_overlay_text,
)


def test_escape_drawtext_text_escapes_filter_control_characters() -> None:
    text = "A: don't, 100%\\safe"

    escaped = escape_drawtext_text(text)

    assert escaped == "A\\: don\\'t\\, 100\\%\\\\safe"


def test_wrap_overlay_text_preserves_manual_lines_and_wraps_long_lines() -> None:
    text = "A house\nB very long option for a compact vertical quiz frame"

    wrapped = wrap_overlay_text(text, max_line_chars=18)

    assert wrapped.splitlines() == [
        "A house",
        "B very long option",
        "for a compact",
        "vertical quiz",
        "frame",
    ]


def test_drawtext_filter_uses_wrapped_escaped_text() -> None:
    overlay = TextOverlay(text="A: Haus, Wohnung", max_line_chars=12)

    ffmpeg_filter = drawtext_filter(overlay)

    assert "drawtext=text='A\\: Haus\\,\\nWohnung'" in ffmpeg_filter
    assert "fontsize=64" in ffmpeg_filter


def test_text_overlay_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        TextOverlay(text="  ")
