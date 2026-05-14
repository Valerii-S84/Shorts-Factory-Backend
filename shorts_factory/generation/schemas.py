from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class FrameType(StrEnum):
    HOOK = "hook"
    QUESTION = "question"
    OPTIONS = "options"
    PAUSE = "pause"
    ANSWER = "answer"
    CTA = "cta"


class ScriptFrame(BaseModel):
    type: FrameType
    text: str
    image_prompt: str

    @field_validator("text", "image_prompt")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Script frame fields must not be empty.")
        return stripped

    @field_validator("image_prompt")
    @classmethod
    def reject_text_in_image_prompt(cls, value: str) -> str:
        forbidden = ["text", "words", "letters", "question", "answer options", "schrift"]
        lowered = value.lower()
        if any(token in lowered for token in forbidden):
            raise ValueError("Image prompts must not ask the image model to draw text.")
        return value


class GeneratedScript(BaseModel):
    hook: str
    voiceover: str
    frames: list[ScriptFrame] = Field(min_length=3, max_length=6)
    telegram_caption: str
    youtube_title: str
    youtube_description: str

    @field_validator("hook", "voiceover", "telegram_caption", "youtube_title")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Generated script text fields must not be empty.")
        return stripped

    @model_validator(mode="after")
    def require_question_and_answer_frames(self) -> GeneratedScript:
        frame_types = {frame.type for frame in self.frames}
        required = {FrameType.QUESTION, FrameType.OPTIONS, FrameType.ANSWER}
        if not required.issubset(frame_types):
            raise ValueError("Script must contain question, options, and answer frames.")
        return self
