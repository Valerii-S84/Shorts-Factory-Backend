import httpx
import pytest

from shorts_factory.quiz_bank.client import QuizBankClient
from shorts_factory.settings import Settings


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


def quiz_bank_settings() -> Settings:
    return Settings(
        environment="test",
        quiz_bank_base_url="https://api.valerchik.de",
        quiz_bank_edge_api_key="edge-token",
        quiz_bank_consumer_id="shorts_factory_backend",
        quiz_bank_api_key="bank-token",
        quiz_bank_quota_key="quota-token",
    )


def test_quiz_bank_client_fetches_manual_quiz_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/quiz-items/item-1"
        return httpx.Response(200, json=quiz_bank_item_payload())

    client = QuizBankClient(
        quiz_bank_settings(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    quiz = client.fetch_quiz("item-1")

    assert quiz.quiz_id == "item-1"
    assert quiz.correct_option_label == "B"
    assert quiz.delivery_id is None


@pytest.mark.parametrize("outcome", ["sent", "failed", "cancelled"])
def test_quiz_bank_client_posts_delivery_outcome(outcome: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = QuizBankClient(
        quiz_bank_settings(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.report_delivery_outcome("delivery-1", outcome)

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/deliveries/delivery-1/outcome"
    assert requests[0].content == f'{{"status":"{outcome}"}}'.encode()


def test_quiz_bank_client_posts_delivery_outcome_reason() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = QuizBankClient(
        quiz_bank_settings(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.report_delivery_outcome(
        "delivery-1",
        "cancelled",
        reason="controlled_live_smoke_no_publish",
    )

    assert requests[0].content == (
        b'{"status":"cancelled","reason":"controlled_live_smoke_no_publish"}'
    )
