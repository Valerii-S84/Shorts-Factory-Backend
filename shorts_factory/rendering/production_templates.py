from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shorts_factory.generation.schemas import PRODUCTION_FRAME_SEQUENCE, FrameType

PRODUCTION_DURATION_MIN_SEC: Final = 14.0
PRODUCTION_DURATION_MAX_SEC: Final = 17.0

DEFAULT_SEGMENT_DURATIONS: Final = {
    FrameType.QUESTION: 5.0,
    FrameType.OPTIONS: 5.0,
    FrameType.ANSWER: 5.5,
}


@dataclass(frozen=True)
class ProductionTemplate:
    template_id: str
    ordered_segment_sequence: tuple[FrameType, ...]
    durations: dict[FrameType, float]
    answer_reveal_at_sec: float
    explanation_required: bool
    has_countdown: bool = False
    has_cta: bool = False
    is_legacy: bool = False

    @property
    def duration_sec(self) -> float:
        return sum(self.durations[frame_type] for frame_type in self.ordered_segment_sequence)

    @property
    def image_count(self) -> int:
        return len(self.ordered_segment_sequence)


PRODUCTION_TEMPLATES: Final = {
    template_id: ProductionTemplate(
        template_id=template_id,
        ordered_segment_sequence=PRODUCTION_FRAME_SEQUENCE,
        durations=DEFAULT_SEGMENT_DURATIONS,
        answer_reveal_at_sec=10.0,
        explanation_required=True,
    )
    for template_id in ("mistake", "level_test", "speed", "grammar_trap", "alltag")
}

TEMPLATE_ROTATION: Final = tuple(PRODUCTION_TEMPLATES)


@dataclass(frozen=True)
class CreativeSelection:
    template: ProductionTemplate


def get_template(template_id: str) -> ProductionTemplate:
    try:
        return PRODUCTION_TEMPLATES[template_id]
    except KeyError as error:
        raise ValueError(f"Unknown production template: {template_id}") from error


def select_creative(
    *,
    job_id: int,
    quiz_level: str | None,
    quiz_topic: str | None,
) -> CreativeSelection:
    return CreativeSelection(
        template=get_template(_select_template_id(job_id, quiz_level, quiz_topic))
    )


def validate_production_frame_order(frame_types: tuple[FrameType, ...]) -> None:
    if frame_types != PRODUCTION_FRAME_SEQUENCE:
        expected = " -> ".join(frame_type.value for frame_type in PRODUCTION_FRAME_SEQUENCE)
        actual = " -> ".join(frame_type.value for frame_type in frame_types)
        raise ValueError(f"Production frame order must be {expected}; got {actual}.")


def _select_template_id(job_id: int, quiz_level: str | None, quiz_topic: str | None) -> str:
    topic = (quiz_topic or "").casefold()
    if any(marker in topic for marker in ("alltag", "situation", "supermarkt", "arzt")):
        return "alltag"
    if any(marker in topic for marker in ("artikel", "grammatik", "dativ", "akkusativ")):
        return "grammar_trap"
    if any(marker in topic for marker in ("vocabulary", "vokabel", "wortschatz")):
        return "speed"
    if quiz_level:
        return "level_test"
    return TEMPLATE_ROTATION[(job_id - 1) % len(TEMPLATE_ROTATION)]
