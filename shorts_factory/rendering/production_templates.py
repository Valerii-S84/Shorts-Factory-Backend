from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shorts_factory.generation.schemas import PRODUCTION_FRAME_SEQUENCE, FrameType

PRODUCTION_DURATION_MIN_SEC: Final = 16.0
PRODUCTION_DURATION_MAX_SEC: Final = 18.0
CTA_MIN_DURATION_SEC: Final = 2.0

DEFAULT_SEGMENT_DURATIONS: Final = {
    FrameType.HOOK: 1.5,
    FrameType.QUESTION: 2.5,
    FrameType.OPTIONS: 5.0,
    FrameType.PAUSE: 3.0,
    FrameType.ANSWER: 3.5,
    FrameType.CTA: 2.0,
}


@dataclass(frozen=True)
class TextVariant:
    variant_id: str
    text: str


@dataclass(frozen=True)
class ProductionTemplate:
    template_id: str
    ordered_segment_sequence: tuple[FrameType, ...]
    durations: dict[FrameType, float]
    allowed_hook_variants: tuple[TextVariant, ...]
    allowed_cta_variant_ids: tuple[str, ...]
    answer_reveal_at_sec: float
    countdown_required: bool
    explanation_required: bool

    @property
    def duration_sec(self) -> float:
        return sum(self.durations[frame_type] for frame_type in self.ordered_segment_sequence)


CTA_VARIANTS: Final = {
    "cta_more_quiz": TextVariant(
        variant_id="cta_more_quiz",
        text="Mehr Deutsch-Quiz im Telegram-Kanal",
    ),
    "cta_daily_tests": TextVariant(
        variant_id="cta_daily_tests",
        text="Täglich neue Deutsch-Tests im Kanal",
    ),
    "cta_link_profile": TextVariant(
        variant_id="cta_link_profile",
        text="Link im Profil - teste dein Deutsch weiter",
    ),
    "cta_grammar_traps": TextVariant(
        variant_id="cta_grammar_traps",
        text="Mehr Grammatik-Fallen im Kanal",
    ),
    "cta_daily_channel": TextVariant(
        variant_id="cta_daily_channel",
        text="Teste dein Deutsch jeden Tag im Kanal",
    ),
}

PRODUCTION_TEMPLATES: Final = {
    "mistake": ProductionTemplate(
        template_id="mistake",
        ordered_segment_sequence=PRODUCTION_FRAME_SEQUENCE,
        durations=DEFAULT_SEGMENT_DURATIONS,
        allowed_hook_variants=(
            TextVariant("h_mistake_90", "90% machen hier einen Fehler"),
            TextVariant("h_mistake_trap", "Vorsicht: Das ist eine Falle"),
        ),
        allowed_cta_variant_ids=("cta_more_quiz", "cta_daily_channel"),
        answer_reveal_at_sec=12.0,
        countdown_required=True,
        explanation_required=True,
    ),
    "level_test": ProductionTemplate(
        template_id="level_test",
        ordered_segment_sequence=PRODUCTION_FRAME_SEQUENCE,
        durations=DEFAULT_SEGMENT_DURATIONS,
        allowed_hook_variants=(
            TextVariant("h_level_a1_b1", "A1 oder B1? Teste dich!"),
            TextVariant("h_level_test", "Welches Deutsch-Level hast du?"),
        ),
        allowed_cta_variant_ids=("cta_daily_tests", "cta_link_profile"),
        answer_reveal_at_sec=12.0,
        countdown_required=True,
        explanation_required=True,
    ),
    "speed": ProductionTemplate(
        template_id="speed",
        ordered_segment_sequence=PRODUCTION_FRAME_SEQUENCE,
        durations=DEFAULT_SEGMENT_DURATIONS,
        allowed_hook_variants=(
            TextVariant("h_speed_5sec", "5 Sekunden - welche Antwort?"),
            TextVariant("h_speed_ab", "Schnell: A, B oder C?"),
        ),
        allowed_cta_variant_ids=("cta_more_quiz", "cta_daily_tests"),
        answer_reveal_at_sec=12.0,
        countdown_required=True,
        explanation_required=True,
    ),
    "grammar_trap": ProductionTemplate(
        template_id="grammar_trap",
        ordered_segment_sequence=PRODUCTION_FRAME_SEQUENCE,
        durations=DEFAULT_SEGMENT_DURATIONS,
        allowed_hook_variants=(
            TextVariant("h_article", "Der, die oder das?"),
            TextVariant("h_grammar_trap", "Diese Grammatik-Falle ist gemein"),
        ),
        allowed_cta_variant_ids=("cta_grammar_traps", "cta_more_quiz"),
        answer_reveal_at_sec=12.0,
        countdown_required=True,
        explanation_required=True,
    ),
    "alltag": ProductionTemplate(
        template_id="alltag",
        ordered_segment_sequence=PRODUCTION_FRAME_SEQUENCE,
        durations=DEFAULT_SEGMENT_DURATIONS,
        allowed_hook_variants=(
            TextVariant("h_alltag", "Im Alltag: Was passt?"),
            TextVariant("h_alltag_context", "Welche Antwort passt hier?"),
        ),
        allowed_cta_variant_ids=("cta_link_profile", "cta_daily_channel"),
        answer_reveal_at_sec=12.0,
        countdown_required=True,
        explanation_required=True,
    ),
}

TEMPLATE_ROTATION: Final = tuple(PRODUCTION_TEMPLATES)


@dataclass(frozen=True)
class CreativeSelection:
    template: ProductionTemplate
    hook_variant: TextVariant
    cta_variant: TextVariant


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
    template = get_template(_select_template_id(job_id, quiz_level, quiz_topic))
    hook_variant = _rotating_choice(template.allowed_hook_variants, job_id)
    cta_variant_id = _rotating_choice(template.allowed_cta_variant_ids, job_id)
    return CreativeSelection(
        template=template,
        hook_variant=hook_variant,
        cta_variant=CTA_VARIANTS[cta_variant_id],
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


def _rotating_choice[T](items: tuple[T, ...], job_id: int) -> T:
    if not items:
        raise ValueError("Cannot rotate an empty variant list.")
    return items[(job_id - 1) % len(items)]
