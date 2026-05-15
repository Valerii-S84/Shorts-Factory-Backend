from __future__ import annotations

from string import ascii_uppercase

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from shorts_factory.quiz_bank.schemas import AnswerOption, ApprovedQuizStatus, Quiz


class QuizBankFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    correct_answer_id: str = Field(
        validation_alias=AliasChoices("correctAnswerId", "correct_answer_id")
    )
    explanation: str

    @field_validator("correct_answer_id", "explanation")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Quiz Bank feedback fields must not be empty.")
        return stripped


class QuizBankOption(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    option_id: str = Field(validation_alias=AliasChoices("id", "optionId", "option_id"))
    text: str = Field(validation_alias=AliasChoices("text", "value", "title"))

    @field_validator("option_id", "text")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Quiz Bank option fields must not be empty.")
        return stripped


class QuizBankItem(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    item_id: str = Field(validation_alias=AliasChoices("item_id", "itemId", "id"))
    question: str
    options: list[QuizBankOption]
    feedback: QuizBankFeedback
    level: str = Field(validation_alias=AliasChoices("level", "cefr_level"))
    topic: str = Field(validation_alias=AliasChoices("topic", "theme"))
    status: ApprovedQuizStatus

    @field_validator("question", mode="before")
    @classmethod
    def parse_question(cls, value: object) -> object:
        if isinstance(value, dict):
            return value.get("text")
        return value

    @field_validator("topic", mode="before")
    @classmethod
    def parse_topic(cls, value: object) -> object:
        if isinstance(value, dict):
            return value.get("title") or value.get("slug") or value.get("id")
        return value

    @field_validator("item_id", "question", "level", "topic")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Quiz Bank item fields must not be empty.")
        return stripped


class QuizBankNextResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    delivery_id: str = Field(validation_alias=AliasChoices("delivery_id", "deliveryId"))
    quiz_item: QuizBankItem = Field(validation_alias=AliasChoices("quiz_item", "quizItem"))

    @field_validator("delivery_id")
    @classmethod
    def require_delivery_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Quiz Bank delivery id must not be empty.")
        return stripped


def quiz_from_next_payload(payload: object) -> Quiz:
    next_response = QuizBankNextResponse.model_validate(payload)
    return quiz_from_item(next_response.quiz_item, delivery_id=next_response.delivery_id)


def quiz_from_item_payload(payload: object) -> Quiz:
    if isinstance(payload, dict) and "quiz_item" in payload:
        payload = payload["quiz_item"]
    return quiz_from_item(QuizBankItem.model_validate(payload))


def quiz_from_item(item: QuizBankItem, *, delivery_id: str | None = None) -> Quiz:
    labels_by_option_id = _labels_by_option_id(item.options)
    if item.feedback.correct_answer_id not in labels_by_option_id:
        raise ValueError("Quiz Bank correctAnswerId must match one answer option id.")
    correct_option_label = labels_by_option_id[item.feedback.correct_answer_id]

    return Quiz(
        quiz_id=item.item_id,
        question=item.question,
        options=[
            AnswerOption(label=labels_by_option_id[option.option_id], text=option.text)
            for option in item.options
        ],
        correct_option_label=correct_option_label,
        explanation=item.feedback.explanation,
        level=item.level,
        topic=item.topic,
        status=item.status,
        delivery_id=delivery_id,
    )


def _labels_by_option_id(options: list[QuizBankOption]) -> dict[str, str]:
    if len(options) > len(ascii_uppercase):
        raise ValueError("Quiz Bank item has too many answer options.")

    labels_by_option_id: dict[str, str] = {}
    for index, option in enumerate(options):
        if option.option_id in labels_by_option_id:
            raise ValueError("Quiz Bank item contains duplicate option ids.")
        labels_by_option_id[option.option_id] = ascii_uppercase[index]
    return labels_by_option_id
