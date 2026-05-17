import pytest
from pydantic import ValidationError

from shorts_factory.rendering.text_overlay import (
    OverlayKind,
    TextOverlay,
    build_text_overlay,
    drawtext_filter,
    drawtext_filters,
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


def test_build_text_overlay_uses_distinct_layouts() -> None:
    hook = build_text_overlay(OverlayKind.HOOK, "90% machen hier einen Fehler")
    answer = build_text_overlay(OverlayKind.ANSWER, "Richtig: A die\nBrücke ist feminin.")

    assert hook.kind == OverlayKind.HOOK
    assert answer.kind == OverlayKind.ANSWER
    assert hook.y != answer.y
    assert hook.box_color != answer.box_color


def test_countdown_overlay_renders_timed_drawtext_filters() -> None:
    overlay = build_text_overlay(OverlayKind.COUNTDOWN, "3\n2\n1")

    filters = drawtext_filters(overlay)

    assert len(filters) == 3
    assert "text='3'" in filters[0]
    assert "enable='between(t,0.0,1.0)'" in filters[0]
    assert "text='2'" in filters[1]
    assert "text='1'" in filters[2]


def test_long_a2_question_overlay_stays_inside_layout_limits() -> None:
    overlay = build_text_overlay(
        OverlayKind.QUESTION,
        "Warum muss man den Termin beim Arzt manchmal auf einen anderen Tag verschieben?",
    )

    assert overlay.kind == OverlayKind.QUESTION
    assert not overlay.has_overflow_risk
    assert len(overlay.wrapped_lines) <= overlay.max_lines
    assert overlay.font_size >= 24


def test_options_overlay_fits_four_structured_rows() -> None:
    overlay = build_text_overlay(
        OverlayKind.OPTIONS,
        "A  den Termin verschieben\n"
        "B  puenktlich ankommen\n"
        "C  eine Rechnung bezahlen\n"
        "D  das Fenster oeffnen",
    )

    assert overlay.kind == OverlayKind.OPTIONS
    assert not overlay.has_overflow_risk
    assert len(overlay.wrapped_lines) <= overlay.max_lines


def test_wrap_overlay_text_splits_long_german_words_to_control_layout() -> None:
    wrapped = wrap_overlay_text("Donaudampfschifffahrtsgesellschaftskapitaen", 12)

    assert all(len(line) <= 12 for line in wrapped.splitlines())
