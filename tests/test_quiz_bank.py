import pytest
from pydantic import ValidationError

from shorts_factory.quiz_bank.schemas import Quiz


def quiz_payload() -> dict[str, object]:
    return {
        "id": "quiz-1",
        "question": "Was bedeutet 'Haus'?",
        "options": [
            {"label": "A", "text": "house"},
            {"label": "B", "text": "car"},
        ],
        "correct_answer": "A",
        "explanation": "Haus bedeutet house.",
        "level": "A1",
        "topic": "Vocabulary",
        "status": "approved",
    }


def test_quiz_accepts_approved_payload_and_exposes_correct_answer() -> None:
    quiz = Quiz.model_validate(quiz_payload())

    assert quiz.quiz_id == "quiz-1"
    assert quiz.correct_option.text == "house"


def test_quiz_rejects_unapproved_status() -> None:
    payload = quiz_payload()
    payload["status"] = "draft"

    with pytest.raises(ValidationError):
        Quiz.model_validate(payload)


def test_quiz_rejects_missing_correct_answer_option() -> None:
    payload = quiz_payload()
    payload["correct_answer"] = "C"

    with pytest.raises(ValidationError):
        Quiz.model_validate(payload)
