from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

FORBIDDEN_IMAGE_PROMPT_PATTERNS = (
    re.compile(r"(?<!\w)text(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)words?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)letters?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)captions?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)question\s+text(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)answer\s+options?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)labels?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)signs?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)ui(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)logos?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)watermarks?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)schrift(?!\w)", re.IGNORECASE),
)


class FrameType(StrEnum):
    HOOK = "hook"
    QUESTION = "question"
    OPTIONS = "options"
    PAUSE = "pause"
    ANSWER = "answer"
    CTA = "cta"


PRODUCTION_FRAME_SEQUENCE = (
    FrameType.QUESTION,
    FrameType.OPTIONS,
    FrameType.ANSWER,
)


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
        if any(pattern.search(value) for pattern in FORBIDDEN_IMAGE_PROMPT_PATTERNS):
            raise ValueError("Image prompts must not ask the image model to draw text.")
        return value


class GeneratedScript(BaseModel):
    frames: list[ScriptFrame] = Field(min_length=3, max_length=3)
    telegram_caption: str
    youtube_title: str
    youtube_description: str

    @field_validator("telegram_caption", "youtube_title")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Generated script text fields must not be empty.")
        return stripped

    @model_validator(mode="after")
    def require_production_frame_order(self) -> GeneratedScript:
        frame_types = tuple(frame.type for frame in self.frames)
        if frame_types != PRODUCTION_FRAME_SEQUENCE:
            expected = " -> ".join(frame_type.value for frame_type in PRODUCTION_FRAME_SEQUENCE)
            raise ValueError(f"Production script frame order must be: {expected}.")
        return self
