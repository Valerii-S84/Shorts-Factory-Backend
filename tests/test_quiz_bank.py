import httpx
import pytest
from pydantic import ValidationError

from shorts_factory.quiz_bank.adapter import quiz_from_item_payload
from shorts_factory.quiz_bank.client import QuizBankClient, QuizBankConfigurationError
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings


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


def quiz_bank_item_payload() -> dict[str, object]:
    return {
        "id": "item-1",
        "question": "Welcher Artikel passt zu Brücke?",
        "options": [
            {"id": "option-der", "text": "der"},
            {"id": "option-die", "text": "die"},
            {"id": "option-das", "text": "das"},
        ],
        "feedback": {
            "correctAnswerId": "option-die",
            "explanation": "Brücke ist feminin: die Brücke.",
        },
        "level": "A1",
        "theme": "Artikel",
        "status": "approved",
    }


def real_quiz_bank_item_payload() -> dict[str, object]:
    payload = quiz_bank_item_payload()
    payload["question"] = {
        "text": "Welcher Artikel passt zu Brücke?",
        "prompt": "",
        "stem": "Welcher Artikel passt zu Brücke?",
    }
    payload["cefr_level"] = payload.pop("level")
    payload["theme"] = {"id": "T01", "title": "Artikel", "slug": "artikel"}
    return payload


def quiz_bank_settings() -> Settings:
    return Settings(
        environment="test",
        quiz_bank_base_url="https://api.valerchik.de",
        quiz_bank_edge_api_key="edge-token",
        quiz_bank_consumer_id="shorts_factory_backend",
        quiz_bank_api_key="bank-token",
        quiz_bank_quota_key="quota-token",
    )


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


def test_quiz_bank_client_posts_trusted_next_quiz() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/quiz-items/next"
        assert request.headers["X-API-Key"] == "edge-token"
        assert request.headers["X-Consumer-Id"] == "shorts_factory_backend"
        assert request.headers["X-QuizBank-API-Key"] == "bank-token"
        assert request.headers["X-QuizBank-Quota-Key"] == "quota-token"
        assert request.content == b'{"consumer_id":"shorts_factory_backend"}'
        return httpx.Response(
            200,
            json={"delivery_id": "delivery-1", "quiz_item": quiz_bank_item_payload()},
        )

    client = QuizBankClient(
        quiz_bank_settings(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    quiz = client.fetch_next_approved_quiz()

    assert quiz.quiz_id == "item-1"
    assert quiz.correct_option_label == "B"
    assert quiz.correct_option.text == "die"
    assert quiz.delivery_id == "delivery-1"


def test_quiz_bank_client_posts_configured_selection_without_hardcoded_levels() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == (
            b'{"consumer_id":"shorts_factory_backend",'
            b'"cefr_level":"custom-level","theme_ids":["custom-theme"]}'
        )
        return httpx.Response(
            200,
            json={"delivery_id": "delivery-1", "quiz_item": quiz_bank_item_payload()},
        )

    settings = quiz_bank_settings()
    settings.quiz_bank_default_levels = ["custom-level"]
    settings.quiz_bank_default_themes = ["custom-theme"]
    client = QuizBankClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.fetch_next_approved_quiz().quiz_id == "item-1"


def test_quiz_bank_client_rejects_missing_auth() -> None:
    client = QuizBankClient(
        Settings(environment="test", quiz_bank_base_url="https://api.valerchik.de"),
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ),
    )

    with pytest.raises(QuizBankConfigurationError) as error:
        client.fetch_next_approved_quiz()

    message = str(error.value)
    assert "QUIZ_BANK_EDGE_API_KEY" in message
    assert "QUIZ_BANK_API_KEY" in message


def test_quiz_bank_adapter_maps_item_payload_to_internal_quiz() -> None:
    quiz = quiz_from_item_payload(quiz_bank_item_payload())

    assert quiz.quiz_id == "item-1"
    assert quiz.question == "Welcher Artikel passt zu Brücke?"
    assert [option.label for option in quiz.options] == ["A", "B", "C"]
    assert [option.text for option in quiz.options] == ["der", "die", "das"]
    assert quiz.correct_option_label == "B"
    assert quiz.explanation == "Brücke ist feminin: die Brücke."
    assert quiz.level == "A1"
    assert quiz.topic == "Artikel"
    assert quiz.status == "approved"


def test_quiz_bank_adapter_maps_real_item_projection_to_internal_quiz() -> None:
    quiz = quiz_from_item_payload(real_quiz_bank_item_payload())

    assert quiz.quiz_id == "item-1"
    assert quiz.question == "Welcher Artikel passt zu Brücke?"
    assert quiz.correct_option_label == "B"
    assert quiz.level == "A1"
    assert quiz.topic == "Artikel"


def test_quiz_bank_adapter_maps_trusted_get_response_wrapper() -> None:
    quiz = quiz_from_item_payload({"quiz_item": real_quiz_bank_item_payload()})

    assert quiz.quiz_id == "item-1"
    assert quiz.correct_option_label == "B"
