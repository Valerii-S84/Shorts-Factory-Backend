import pytest

from shorts_factory.generation.schemas import PRODUCTION_FRAME_SEQUENCE, FrameType
from shorts_factory.rendering.production_templates import (
    PRODUCTION_DURATION_MAX_SEC,
    PRODUCTION_DURATION_MIN_SEC,
    PRODUCTION_TEMPLATES,
    select_creative,
)


def test_production_frame_sequence_is_only_question_options_answer() -> None:
    assert PRODUCTION_FRAME_SEQUENCE == (
        FrameType.QUESTION,
        FrameType.OPTIONS,
        FrameType.ANSWER,
    )
    assert len(PRODUCTION_FRAME_SEQUENCE) == 3
    assert {frame.value for frame in PRODUCTION_FRAME_SEQUENCE}.isdisjoint({"hook", "pause", "cta"})


def test_production_duration_range_matches_three_frame_contract() -> None:
    assert PRODUCTION_DURATION_MIN_SEC == 14.0
    assert PRODUCTION_DURATION_MAX_SEC == 17.0


@pytest.mark.parametrize(
    "template_id", ["mistake", "level_test", "speed", "grammar_trap", "alltag"]
)
def test_each_production_template_defines_required_contract(template_id: str) -> None:
    template = PRODUCTION_TEMPLATES[template_id]

    assert template.ordered_segment_sequence == PRODUCTION_FRAME_SEQUENCE
    assert PRODUCTION_DURATION_MIN_SEC <= template.duration_sec <= PRODUCTION_DURATION_MAX_SEC
    assert template.duration_sec == 15.5
    assert template.image_count == 3
    assert template.answer_reveal_at_sec == 10.0
    assert not template.has_countdown
    assert not template.has_cta
    assert template.explanation_required


def test_topic_selection_keeps_grammar_template() -> None:
    first = select_creative(job_id=1, quiz_level="A1", quiz_topic="Artikel")
    second = select_creative(job_id=2, quiz_level="A1", quiz_topic="Artikel")

    assert first.template.template_id == "grammar_trap"
    assert second.template.template_id == "grammar_trap"


def test_topic_selection_keeps_alltag_template() -> None:
    first = select_creative(job_id=1, quiz_level="A1", quiz_topic="Alltag")
    second = select_creative(job_id=2, quiz_level="A1", quiz_topic="Alltag")

    assert first.template.template_id == "alltag"
    assert second.template.template_id == "alltag"
