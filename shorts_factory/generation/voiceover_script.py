from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, Field, model_validator

from shorts_factory.quiz_bank.schemas import AnswerOption, Quiz

QUESTION_SEGMENT_SEC: Final = 5.0
OPTIONS_SEGMENT_SEC: Final = 5.0
ANSWER_SEGMENT_SEC: Final = 5.5
VOICEOVER_TOTAL_DURATION_SEC: Final = 15.5
VOICEOVER_PART_PAUSE_SEC: Final = 0.35
VOICEOVER_WORDS_PER_MINUTE: Final = 180.0
VOICEOVER_EXPLANATION_MAX_CHARS: Final = 90
EXPLANATION_FALLBACK_CHAR_LIMITS: Final = (80, 72, 64, 56, 48, 40, 32, 24, 18)
EXPLANATION_BOUNDARY_MIN_CHARS: Final = 12
VOICEOVER_PART_SEQUENCE: Final = ("question", "options", "answer")
FORBIDDEN_NARRATION_PATTERNS: Final = (
    re.compile(r"\btelegram\b", re.IGNORECASE),
    re.compile(r"\bcountdown\b", re.IGNORECASE),
    re.compile(r"\bmehr\s+deutsch-quiz\b", re.IGNORECASE),
    re.compile(r"\blink\s+im\s+profil\b", re.IGNORECASE),
)


class VoiceoverScriptError(RuntimeError):
    pass


class VoiceoverPart(BaseModel):
    kind: Literal["question", "options", "answer"]
    text: str
    starts_at_sec: float
    duration_sec: float
    estimated_duration_sec: float

    @model_validator(mode="after")
    def require_non_empty_text(self) -> VoiceoverPart:
        if not self.text.strip():
            raise ValueError("Voiceover part text must not be empty.")
        return self


class VoiceoverPlan(BaseModel):
    parts: list[VoiceoverPart] = Field(min_length=3, max_length=3)
    text: str
    explanation_excerpt: str
    estimated_duration_sec: float
    narration_contains_question: bool
    narration_contains_all_options: bool
    narration_contains_correct_answer: bool

    @model_validator(mode="after")
    def require_canonical_parts(self) -> VoiceoverPlan:
        actual = tuple(part.kind for part in self.parts)
        if actual != VOICEOVER_PART_SEQUENCE:
            expected = " -> ".join(VOICEOVER_PART_SEQUENCE)
            got = " -> ".join(actual)
            raise ValueError(f"Voiceover parts must be {expected}; got {got}.")
        return self


def build_voiceover_plan(quiz: Quiz, *, speed: float = 0.8) -> VoiceoverPlan:
    _validate_speed(speed)
    question_text = quiz.question
    options_text = _options_text(_ordered_options(quiz.options))
    answer_prefix = f"Richtig ist {quiz.correct_option_label}: {quiz.correct_option.text}."
    explanation_excerpt = _fit_explanation_excerpt(
        quiz.explanation,
        immutable_parts=(question_text, options_text, answer_prefix),
        speed=speed,
    )
    answer_text = f"{answer_prefix} {explanation_excerpt}".strip()
    parts = [
        _part("question", question_text, 0.0, QUESTION_SEGMENT_SEC, speed),
        _part("options", options_text, QUESTION_SEGMENT_SEC, OPTIONS_SEGMENT_SEC, speed),
        _part(
            "answer",
            answer_text,
            QUESTION_SEGMENT_SEC + OPTIONS_SEGMENT_SEC,
            ANSWER_SEGMENT_SEC,
            speed,
        ),
    ]
    text = "\n\n".join(part.text for part in parts)
    plan = VoiceoverPlan(
        parts=parts,
        text=text,
        explanation_excerpt=explanation_excerpt,
        estimated_duration_sec=_estimate_parts_duration(parts),
        narration_contains_question=question_text in text,
        narration_contains_all_options=_contains_all_options(parts[1].text, quiz.options),
        narration_contains_correct_answer=_answer_reveal_phrase(quiz) in parts[2].text,
    )
    validate_voiceover_plan(plan, quiz)
    return plan


def validate_voiceover_plan(plan: VoiceoverPlan, quiz: Quiz) -> None:
    if len(plan.parts) != 3:
        raise VoiceoverScriptError("Voiceover must contain exactly 3 narration parts.")
    if plan.estimated_duration_sec > VOICEOVER_TOTAL_DURATION_SEC:
        raise VoiceoverScriptError("Voiceover estimated reading time exceeds video duration.")
    if any(pattern.search(plan.text) for pattern in FORBIDDEN_NARRATION_PATTERNS):
        raise VoiceoverScriptError("Voiceover contains forbidden CTA or channel wording.")

    question_part, options_part, answer_part = plan.parts
    if quiz.question not in question_part.text:
        raise VoiceoverScriptError(
            "Voiceover question part does not contain the Quiz Bank question."
        )
    if not _contains_all_options(options_part.text, quiz.options):
        raise VoiceoverScriptError("Voiceover options part does not contain all answer options.")
    _validate_option_order(options_part.text, quiz.options)
    _validate_answer_reveal(answer_part.text, quiz)
    _validate_answer_not_revealed_early(plan, quiz)
    _validate_explanation_excerpt(plan.explanation_excerpt, quiz)


def estimate_reading_time_sec(text: str, *, speed: float = 0.8, pause_count: int = 0) -> float:
    _validate_speed(speed)
    words = re.findall(r"\S+", text)
    if not words:
        return 0.0
    words_per_second = (VOICEOVER_WORDS_PER_MINUTE * speed) / 60
    return len(words) / words_per_second + pause_count * VOICEOVER_PART_PAUSE_SEC


def _part(
    kind: Literal["question", "options", "answer"],
    text: str,
    starts_at_sec: float,
    duration_sec: float,
    speed: float,
) -> VoiceoverPart:
    return VoiceoverPart(
        kind=kind,
        text=text,
        starts_at_sec=starts_at_sec,
        duration_sec=duration_sec,
        estimated_duration_sec=estimate_reading_time_sec(text, speed=speed),
    )


def _ordered_options(options: list[AnswerOption]) -> list[AnswerOption]:
    return sorted(options, key=lambda option: option.label)


def _options_text(options: list[AnswerOption]) -> str:
    return " ".join(f"{option.label}: {option.text}." for option in options)


def _fit_explanation_excerpt(
    explanation: str,
    *,
    immutable_parts: tuple[str, str, str],
    speed: float,
) -> str:
    base_text = "\n\n".join(immutable_parts)
    if (
        estimate_reading_time_sec(base_text, speed=speed, pause_count=2)
        > VOICEOVER_TOTAL_DURATION_SEC
    ):
        raise VoiceoverScriptError("Voiceover immutable quiz facts do not fit the video duration.")

    stripped = " ".join(explanation.strip().split())
    for char_limit in _descending_char_limits(stripped):
        excerpt = _trim_explanation_at_boundary(stripped, char_limit)
        candidate = f"{base_text} {excerpt}".strip()
        if (
            estimate_reading_time_sec(candidate, speed=speed, pause_count=2)
            <= VOICEOVER_TOTAL_DURATION_SEC
        ):
            return excerpt
    raise VoiceoverScriptError("Voiceover explanation excerpt does not fit the video duration.")


def _descending_char_limits(explanation: str) -> tuple[int, ...]:
    max_chars = min(len(explanation), VOICEOVER_EXPLANATION_MAX_CHARS)
    limits = {max_chars, *EXPLANATION_FALLBACK_CHAR_LIMITS}
    return tuple(sorted((limit for limit in limits if 0 < limit <= max_chars), reverse=True))


def _trim_explanation_at_boundary(explanation: str, max_chars: int) -> str:
    if len(explanation) <= max_chars:
        return explanation

    sentence_end = _last_boundary_index(explanation, max_chars, ".!?")
    if sentence_end is not None:
        return explanation[:sentence_end].rstrip()

    content_limit = max(1, max_chars - 3)
    phrase_end = _last_boundary_index(explanation, content_limit, ",;:")
    if phrase_end is not None:
        return explanation[:phrase_end].rstrip(" ,;:") + "..."

    word_end = explanation.rfind(" ", 0, content_limit + 1)
    if word_end >= EXPLANATION_BOUNDARY_MIN_CHARS:
        return explanation[:word_end].rstrip(" ,;:") + "..."
    return explanation[:content_limit].rstrip(" ,;:") + "..."


def _last_boundary_index(text: str, max_chars: int, boundary_chars: str) -> int | None:
    for index in range(min(len(text), max_chars) - 1, EXPLANATION_BOUNDARY_MIN_CHARS - 1, -1):
        if text[index] in boundary_chars and (index + 1 == len(text) or text[index + 1].isspace()):
            return index + 1
    return None


def _contains_all_options(text: str, options: list[AnswerOption]) -> bool:
    return all(f"{option.label}: {option.text}" in text for option in options)


def _validate_option_order(text: str, options: list[AnswerOption]) -> None:
    positions = [
        text.find(f"{option.label}: {option.text}") for option in _ordered_options(options)
    ]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise VoiceoverScriptError("Voiceover answer options are not ordered A -> B -> C -> D.")


def _validate_answer_reveal(answer_text: str, quiz: Quiz) -> None:
    phrase = _answer_reveal_phrase(quiz)
    if phrase not in answer_text:
        raise VoiceoverScriptError("Voiceover answer part does not contain the correct answer.")


def _validate_answer_not_revealed_early(plan: VoiceoverPlan, quiz: Quiz) -> None:
    phrase = _answer_reveal_phrase(quiz)
    early_text = "\n\n".join(part.text for part in plan.parts[:2])
    if phrase in early_text:
        raise VoiceoverScriptError("Voiceover reveals the correct answer before the answer part.")


def _validate_explanation_excerpt(excerpt: str, quiz: Quiz) -> None:
    normalized_source = " ".join(quiz.explanation.strip().split())
    if not excerpt.strip():
        raise VoiceoverScriptError("Voiceover answer explanation is missing.")
    if not normalized_source.startswith(excerpt.rstrip(".")):
        raise VoiceoverScriptError("Voiceover explanation is not sourced from Quiz Bank.")


def _answer_reveal_phrase(quiz: Quiz) -> str:
    return f"Richtig ist {quiz.correct_option_label}: {quiz.correct_option.text}"


def _estimate_parts_duration(parts: list[VoiceoverPart]) -> float:
    return sum(part.estimated_duration_sec for part in parts) + VOICEOVER_PART_PAUSE_SEC * 2


def _validate_speed(speed: float) -> None:
    if not 0.25 <= speed <= 4.0:
        raise VoiceoverScriptError("Voiceover speed must be between 0.25 and 4.0.")
