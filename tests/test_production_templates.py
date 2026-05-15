import pytest

from shorts_factory.generation.schemas import PRODUCTION_FRAME_SEQUENCE
from shorts_factory.rendering.production_templates import (
    CTA_MIN_DURATION_SEC,
    CTA_VARIANTS,
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
    assert template.durations[PRODUCTION_FRAME_SEQUENCE[-1]] >= CTA_MIN_DURATION_SEC
    assert template.answer_reveal_at_sec == 12.0
    assert template.countdown_required
    assert template.explanation_required
    assert template.allowed_hook_variants
    assert template.allowed_cta_variant_ids
    assert all(variant_id in CTA_VARIANTS for variant_id in template.allowed_cta_variant_ids)


def test_hook_variant_rotation_is_deterministic_within_template() -> None:
    first = select_creative(job_id=1, quiz_level="A1", quiz_topic="Artikel")
    second = select_creative(job_id=2, quiz_level="A1", quiz_topic="Artikel")

    assert first.template.template_id == "grammar_trap"
    assert second.template.template_id == "grammar_trap"
    assert first.hook_variant.variant_id != second.hook_variant.variant_id


def test_cta_variant_rotation_is_deterministic_within_template() -> None:
    first = select_creative(job_id=1, quiz_level="A1", quiz_topic="Alltag")
    second = select_creative(job_id=2, quiz_level="A1", quiz_topic="Alltag")

    assert first.template.template_id == "alltag"
    assert second.template.template_id == "alltag"
    assert first.cta_variant.variant_id != second.cta_variant.variant_id
