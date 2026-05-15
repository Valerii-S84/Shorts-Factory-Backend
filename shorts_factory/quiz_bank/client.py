from __future__ import annotations

from typing import Literal
from urllib.parse import quote

import httpx

from shorts_factory.quiz_bank.adapter import quiz_from_item_payload, quiz_from_next_payload
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings

DeliveryOutcome = Literal["sent", "failed", "cancelled"]


class QuizBankConfigurationError(RuntimeError):
    pass


class QuizBankClient:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        if settings.quiz_bank_base_url is None:
            raise QuizBankConfigurationError("QUIZ_BANK_BASE_URL is not configured.")
        self._settings = settings
        self._client = http_client or httpx.Client(timeout=20)

    def fetch_next_approved_quiz(self) -> Quiz:
        response = self._client.post(
            self._url(self._settings.quiz_bank_next_path),
            headers=self._auth_headers(),
            json={},
        )
        response.raise_for_status()
        return quiz_from_next_payload(response.json())

    def fetch_quiz(self, quiz_id: str) -> Quiz:
        item_id = quote(quiz_id, safe="")
        response = self._client.get(
            self._url(f"/v1/quiz-items/{item_id}"),
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return quiz_from_item_payload(response.json())

    def report_delivery_outcome(self, delivery_id: str, outcome: DeliveryOutcome) -> None:
        safe_delivery_id = quote(delivery_id, safe="")
        response = self._client.post(
            self._url(f"/v1/deliveries/{safe_delivery_id}/outcome"),
            headers=self._auth_headers(),
            json={"outcome": outcome},
        )
        response.raise_for_status()

    def _url(self, path: str) -> str:
        return f"{self._settings.quiz_bank_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _auth_headers(self) -> dict[str, str]:
        missing = []
        if self._settings.quiz_bank_edge_api_key is None:
            missing.append("QUIZ_BANK_EDGE_API_KEY")
        if not self._settings.quiz_bank_consumer_id.strip():
            missing.append("QUIZ_BANK_CONSUMER_ID")
        if self._settings.quiz_bank_api_key is None:
            missing.append("QUIZ_BANK_API_KEY")
        if missing:
            joined = ", ".join(missing)
            raise QuizBankConfigurationError(f"Missing Quiz Bank auth configuration: {joined}.")

        headers = {
            "X-API-Key": self._settings.quiz_bank_edge_api_key.get_secret_value(),
            "X-Consumer-Id": self._settings.quiz_bank_consumer_id,
            "X-QuizBank-API-Key": self._settings.quiz_bank_api_key.get_secret_value(),
        }
        if self._settings.quiz_bank_quota_key is not None:
            headers["X-QuizBank-Quota-Key"] = self._settings.quiz_bank_quota_key.get_secret_value()
        return headers
