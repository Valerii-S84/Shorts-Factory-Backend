from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

ApprovedQuizStatus = Literal["approved", "published"]


class AnswerOption(BaseModel):
    label: str
    text: str

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Answer option label is required.")
        return normalized

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Answer option text is required.")
        return stripped


class Quiz(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    quiz_id: str = Field(validation_alias=AliasChoices("quiz_id", "id"))
    question: str
    options: list[AnswerOption]
    correct_option_label: str = Field(
        validation_alias=AliasChoices("correct_option_label", "correct_answer", "answer")
    )
    explanation: str
    level: str
    topic: str
    status: ApprovedQuizStatus
    delivery_id: str | None = None

    @field_validator("question", "explanation", "level", "topic")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Quiz text fields must not be empty.")
        return stripped

    @field_validator("correct_option_label")
    @classmethod
    def normalize_correct_label(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Correct answer label is required.")
        return normalized

    @model_validator(mode="after")
    def validate_correct_answer(self) -> Quiz:
        labels = {option.label for option in self.options}
        if len(self.options) < 2:
            raise ValueError("Quiz must contain at least two answer options.")
        if self.correct_option_label not in labels:
            raise ValueError("Correct answer label must match one answer option.")
        return self

    @property
    def correct_option(self) -> AnswerOption:
        for option in self.options:
            if option.label == self.correct_option_label:
                return option
        raise ValueError("Correct answer option is missing.")

    def facts_snapshot(self) -> dict[str, object]:
        return {
            "quiz_id": self.quiz_id,
            "question": self.question,
            "options": [option.model_dump() for option in self.options],
            "correct_option_label": self.correct_option_label,
            "correct_answer_text": self.correct_option.text,
            "explanation": self.explanation,
            "level": self.level,
            "topic": self.topic,
            "status": self.status,
            "delivery_id": self.delivery_id,
        }
