from __future__ import annotations

import httpx

from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings


class QuizBankConfigurationError(RuntimeError):
    pass


class QuizBankClient:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        if settings.quiz_bank_base_url is None:
            raise QuizBankConfigurationError("QUIZ_BANK_BASE_URL is not configured.")
        self._settings = settings
        self._client = http_client or httpx.Client(timeout=20)

    def fetch_next_approved_quiz(self) -> Quiz:
        url = f"{self._settings.quiz_bank_base_url.rstrip('/')}{self._settings.quiz_bank_next_path}"
        headers: dict[str, str] = {}
        if self._settings.quiz_bank_api_key is not None:
            token = self._settings.quiz_bank_api_key.get_secret_value()
            headers["Authorization"] = f"Bearer {token}"

        response = self._client.get(url, headers=headers, params={"status": "approved,published"})
        response.raise_for_status()
        return Quiz.model_validate(response.json())

    def fetch_quiz(self, quiz_id: str) -> Quiz:
        url = f"{self._settings.quiz_bank_base_url.rstrip('/')}/quizzes/{quiz_id}"
        headers: dict[str, str] = {}
        if self._settings.quiz_bank_api_key is not None:
            token = self._settings.quiz_bank_api_key.get_secret_value()
            headers["Authorization"] = f"Bearer {token}"

        response = self._client.get(url, headers=headers)
        response.raise_for_status()
        return Quiz.model_validate(response.json())
