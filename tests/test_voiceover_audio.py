from __future__ import annotations

import pytest

from shorts_factory.generation.voiceover_script import (
    ANSWER_SEGMENT_SEC,
    OPTIONS_SEGMENT_SEC,
    QUESTION_SEGMENT_SEC,
    VOICEOVER_TOTAL_DURATION_SEC,
    VoiceoverScriptError,
    build_voiceover_plan,
    validate_voiceover_plan,
)
from shorts_factory.quiz_bank.schemas import Quiz


def test_voiceover_builder_creates_three_quiz_bank_sourced_parts() -> None:
    source_quiz = quiz()

    plan = build_voiceover_plan(source_quiz)

    assert [part.kind for part in plan.parts] == ["question", "options", "answer"]
    assert plan.text.split("\n\n") == [part.text for part in plan.parts]
    assert source_quiz.question in plan.parts[0].text
    assert "Telegram" not in plan.text
    assert "Countdown" not in plan.text
    assert "Mehr Deutsch-Quiz" not in plan.text
    assert source_quiz.explanation.startswith(plan.explanation_excerpt.rstrip("."))


def test_voiceover_options_reads_all_four_options_in_order_without_reveal() -> None:
    source_quiz = quiz()
    plan = build_voiceover_plan(source_quiz)
    options_part = plan.parts[1].text

    expected_options = [f"{option.label}: {option.text}" for option in source_quiz.options]

    assert all(option in options_part for option in expected_options)
    assert [options_part.index(option) for option in expected_options] == sorted(
        options_part.index(option) for option in expected_options
    )
    assert f"Richtig ist {source_quiz.correct_option_label}" not in options_part


def test_voiceover_answer_reveal_appears_only_in_answer_part() -> None:
    source_quiz = quiz()
    plan = build_voiceover_plan(source_quiz)
    answer_phrase = (
        f"Richtig ist {source_quiz.correct_option_label}: {source_quiz.correct_option.text}"
    )

    assert answer_phrase not in plan.parts[0].text
    assert answer_phrase not in plan.parts[1].text
    assert answer_phrase in plan.parts[2].text
    assert source_quiz.correct_option.text in plan.parts[2].text
    assert plan.explanation_excerpt in plan.parts[2].text


def test_voiceover_timing_uses_canonical_three_segments() -> None:
    plan = build_voiceover_plan(quiz())

    assert plan.parts[0].starts_at_sec == 0.0
    assert plan.parts[0].duration_sec == QUESTION_SEGMENT_SEC
    assert plan.parts[1].starts_at_sec == QUESTION_SEGMENT_SEC
    assert plan.parts[1].duration_sec == OPTIONS_SEGMENT_SEC
    assert plan.parts[2].starts_at_sec == QUESTION_SEGMENT_SEC + OPTIONS_SEGMENT_SEC
    assert plan.parts[2].duration_sec == ANSWER_SEGMENT_SEC
    assert plan.estimated_duration_sec <= VOICEOVER_TOTAL_DURATION_SEC


def test_voiceover_shortens_explanation_first_when_reading_time_is_long() -> None:
    source_quiz = quiz().model_copy(
        update={
            "explanation": (
                "Man legt den Termin auf einen späteren Zeitpunkt, wenn der alte Zeitpunkt "
                "nicht mehr passt und beide Personen einen neuen Termin brauchen. "
                "Die Bedeutung bleibt gleich: Es geht um eine neue Zeit, nicht um Absage."
            )
        }
    )

    plan = build_voiceover_plan(source_quiz)

    assert plan.explanation_excerpt != source_quiz.explanation
    assert plan.estimated_duration_sec <= VOICEOVER_TOTAL_DURATION_SEC
    assert "D: zu Hause bleiben" in plan.parts[1].text
    assert f"Richtig ist {source_quiz.correct_option_label}: {source_quiz.correct_option.text}" in (
        plan.parts[2].text
    )


def test_voiceover_validation_rejects_missing_options() -> None:
    source_quiz = quiz()
    plan = build_voiceover_plan(source_quiz)
    bad_options = plan.parts[1].model_copy(update={"text": "A: absagen. B: anfangen."})
    bad_plan = plan.model_copy(
        update={"parts": [plan.parts[0], bad_options, plan.parts[2]], "text": bad_options.text}
    )

    with pytest.raises(VoiceoverScriptError, match="answer options"):
        validate_voiceover_plan(bad_plan, source_quiz)


def test_voiceover_validation_rejects_answer_reveal_before_answer_part() -> None:
    source_quiz = quiz()
    plan = build_voiceover_plan(source_quiz)
    answer_phrase = (
        f"Richtig ist {source_quiz.correct_option_label}: {source_quiz.correct_option.text}"
    )
    bad_options = plan.parts[1].model_copy(update={"text": f"{plan.parts[1].text} {answer_phrase}"})
    bad_plan = plan.model_copy(update={"parts": [plan.parts[0], bad_options, plan.parts[2]]})

    with pytest.raises(VoiceoverScriptError, match="before the answer"):
        validate_voiceover_plan(bad_plan, source_quiz)


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-a2-termin",
            "question": "Was bedeutet 'einen Termin verschieben'?",
            "options": [
                {"label": "A", "text": "einen Termin absagen"},
                {"label": "B", "text": "einen Termin sofort beginnen"},
                {"label": "C", "text": "einen Termin auf später legen"},
                {"label": "D", "text": "zu Hause bleiben"},
            ],
            "correct_answer": "C",
            "explanation": "Man legt den Termin auf einen späteren Zeitpunkt.",
            "level": "A2",
            "topic": "Alltag",
            "status": "approved",
        }
    )
