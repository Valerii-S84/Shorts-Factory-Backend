import pytest

from shorts_factory.generation.schemas import PRODUCTION_FRAME_SEQUENCE
from shorts_factory.rendering.production_templates import (
    PRODUCTION_DURATION_MAX_SEC,
    PRODUCTION_DURATION_MIN_SEC,
    PRODUCTION_TEMPLATES,
    select_creative,
)


@pytest.mark.parametrize(
    "template_id", ["mistake", "level_test", "speed", "grammar_trap", "alltag"]
)
def test_each_production_template_defines_required_contract(template_id: str) -> None:
    template = PRODUCTION_TEMPLATES[template_id]

    assert template.ordered_segment_sequence == PRODUCTION_FRAME_SEQUENCE
    assert PRODUCTION_DURATION_MIN_SEC <= template.duration_sec <= PRODUCTION_DURATION_MAX_SEC
    assert template.durations[PRODUCTION_FRAME_SEQUENCE[0]] == 5.0
    assert template.durations[PRODUCTION_FRAME_SEQUENCE[1]] == 5.0
    assert template.durations[PRODUCTION_FRAME_SEQUENCE[2]] == 5.5
    assert template.answer_reveal_at_sec == 10.0
    assert template.explanation_required


def test_template_selection_is_deterministic_for_grammar_topic() -> None:
    first = select_creative(job_id=1, quiz_level="A1", quiz_topic="Artikel")
    second = select_creative(job_id=2, quiz_level="A1", quiz_topic="Artikel")

    assert first.template.template_id == "grammar_trap"
    assert second.template.template_id == "grammar_trap"


def test_template_selection_is_deterministic_for_alltag_topic() -> None:
    first = select_creative(job_id=1, quiz_level="A1", quiz_topic="Alltag")
    second = select_creative(job_id=2, quiz_level="A1", quiz_topic="Alltag")

    assert first.template.template_id == "alltag"
    assert second.template.template_id == "alltag"
