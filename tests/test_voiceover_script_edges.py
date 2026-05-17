from __future__ import annotations

import pytest
from pydantic import ValidationError

from shorts_factory.generation.voiceover_script import (
    VoiceoverPart,
    VoiceoverPlan,
    VoiceoverScriptError,
    build_voiceover_plan,
    estimate_reading_time_sec,
    validate_voiceover_plan,
)
from shorts_factory.quiz_bank.schemas import Quiz


def test_voiceover_part_rejects_empty_text() -> None:
    with pytest.raises(ValidationError, match="empty"):
        VoiceoverPart(
            kind="question",
            text=" ",
            starts_at_sec=0,
            duration_sec=5,
            estimated_duration_sec=0,
        )


def test_voiceover_plan_rejects_non_canonical_part_order() -> None:
    parts = [
        VoiceoverPart(
            kind="answer",
            text="answer",
            starts_at_sec=10,
            duration_sec=5.5,
            estimated_duration_sec=1,
        ),
        VoiceoverPart(
            kind="question",
            text="question",
            starts_at_sec=0,
            duration_sec=5,
            estimated_duration_sec=1,
        ),
        VoiceoverPart(
            kind="options",
            text="options",
            starts_at_sec=5,
            duration_sec=5,
            estimated_duration_sec=1,
        ),
    ]

    with pytest.raises(ValidationError, match="question -> options -> answer"):
        VoiceoverPlan(
            parts=parts,
            text="answer\n\nquestion\n\noptions",
            explanation_excerpt="source",
            estimated_duration_sec=3,
            narration_contains_question=True,
            narration_contains_all_options=True,
            narration_contains_correct_answer=True,
        )


def test_estimated_reading_time_handles_empty_text_and_invalid_speed() -> None:
    assert estimate_reading_time_sec("") == 0

    with pytest.raises(VoiceoverScriptError, match="speed"):
        estimate_reading_time_sec("Hallo", speed=0.1)


def test_voiceover_validation_rejects_forbidden_channel_wording() -> None:
    source_quiz = quiz()
    plan = build_voiceover_plan(source_quiz)
    bad_plan = plan.model_copy(update={"text": f"{plan.text}\nTelegram"})

    with pytest.raises(VoiceoverScriptError, match="forbidden"):
        validate_voiceover_plan(bad_plan, source_quiz)


def test_voiceover_validation_rejects_missing_question() -> None:
    source_quiz = quiz()
    plan = build_voiceover_plan(source_quiz)
    bad_question = plan.parts[0].model_copy(update={"text": "Andere Frage?"})
    bad_plan = plan.model_copy(update={"parts": [bad_question, plan.parts[1], plan.parts[2]]})

    with pytest.raises(VoiceoverScriptError, match="question"):
        validate_voiceover_plan(bad_plan, source_quiz)


def test_voiceover_validation_rejects_unsourced_explanation() -> None:
    source_quiz = quiz()
    plan = build_voiceover_plan(source_quiz)
    bad_plan = plan.model_copy(update={"explanation_excerpt": "Das ist frei erfunden."})

    with pytest.raises(VoiceoverScriptError, match="not sourced"):
        validate_voiceover_plan(bad_plan, source_quiz)


def test_voiceover_builder_rejects_immutable_facts_that_do_not_fit() -> None:
    long_text = " ".join(["sehrlang"] * 70)
    source_quiz = Quiz.model_validate(
        {
            "id": "quiz-too-long",
            "question": long_text,
            "options": [
                {"label": "A", "text": long_text},
                {"label": "B", "text": long_text},
            ],
            "correct_answer": "A",
            "explanation": "Quelle.",
            "level": "A2",
            "topic": "Alltag",
            "status": "approved",
        }
    )

    with pytest.raises(VoiceoverScriptError, match="immutable quiz facts"):
        build_voiceover_plan(source_quiz)


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-edge",
            "question": "Was passt?",
            "options": [{"label": "A", "text": "heute"}, {"label": "B", "text": "gestern"}],
            "correct_answer": "A",
            "explanation": "Heute passt in diesem Satz.",
            "level": "A2",
            "topic": "Alltag",
            "status": "approved",
        }
    )
