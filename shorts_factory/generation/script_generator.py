from __future__ import annotations

from typing import Protocol

from openai import OpenAI

from shorts_factory.generation.schemas import FrameType, GeneratedScript
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings


class ScriptGenerationError(RuntimeError):
    pass


class ScriptGenerator(Protocol):
    def generate(self, quiz: Quiz) -> GeneratedScript:
        pass


class OpenAIScriptGenerator:
    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        if settings.openai_api_key is None:
            raise ScriptGenerationError("OPENAI_API_KEY is not configured.")
        self._settings = settings
        self._client = client or OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def generate(self, quiz: Quiz) -> GeneratedScript:
        response = self._client.responses.parse(
            model=self._settings.openai_script_model,
            input=[
                {
                    "role": "system",
                    "content": _system_prompt(),
                },
                {
                    "role": "user",
                    "content": str(quiz.facts_snapshot()),
                },
            ],
            text_format=GeneratedScript,
        )
        script = response.output_parsed
        if script is None:
            raise ScriptGenerationError("OpenAI did not return a parsed script.")
        validate_script_preserves_quiz_facts(script, quiz)
        return script


def validate_script_preserves_quiz_facts(script: GeneratedScript, quiz: Quiz) -> None:
    combined_text = " ".join(frame.text for frame in script.frames)
    if quiz.question not in combined_text:
        raise ScriptGenerationError("Generated script does not preserve the quiz question.")

    options_frames = [frame for frame in script.frames if frame.type == FrameType.OPTIONS]
    options_text = " ".join(frame.text for frame in options_frames)
    for option in quiz.options:
        if option.label not in options_text or option.text not in options_text:
            raise ScriptGenerationError("Generated script does not preserve the answer options.")

    answer_frames = [frame for frame in script.frames if frame.type == FrameType.ANSWER]
    answer_text = " ".join(frame.text for frame in answer_frames)
    if quiz.correct_option_label not in answer_text or quiz.correct_option.text not in answer_text:
        raise ScriptGenerationError("Generated script does not preserve the correct answer.")


def _system_prompt() -> str:
    return (
        "You create German short-video quiz scripts as strict JSON. "
        "The quiz facts are immutable: question, options, correct answer, explanation, "
        "level, and topic must not be changed. Return exactly three frames in this order: "
        "question, options, answer. Frame 1 is the question scene and visible text is only "
        "the quiz question. Frame 2 is the options scene and visible text is only the "
        "A/B/C/D answer options. Frame 3 is the answer scene and visible text is the exact "
        "correct answer plus a short explanation excerpt based on the Quiz Bank explanation. "
        "Do not create a hook, pause, countdown, CTA, channel promo, or marketing text in "
        "the video script. The voiceover must have three short parts: read the question, "
        "read the options, then reveal the correct answer and short explanation. Keep it "
        "concise enough for a 15-16 second video at speech speed 0.8. "
        "For each frame, frame.image_prompt is only a concise scene brief, not a full "
        "style prompt. Do not include style words that conflict with the backend's "
        "centralized image style contract. It must not request visible text, letters, "
        "captions, question text, answer options, labels, signs, UI, logos, watermarks, "
        "or any written content inside images. Telegram/channel promotion belongs only in "
        "captions outside the video."
    )
