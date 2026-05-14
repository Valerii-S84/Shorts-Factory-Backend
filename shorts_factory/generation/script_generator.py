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

    answer_frames = [frame for frame in script.frames if frame.type == FrameType.ANSWER]
    answer_text = " ".join(frame.text for frame in answer_frames)
    if quiz.correct_option_label not in answer_text and quiz.correct_option.text not in answer_text:
        raise ScriptGenerationError("Generated script does not preserve the correct answer.")

    option_text = " ".join(f"{option.label} {option.text}" for option in quiz.options)
    if not all(option.label in option_text for option in quiz.options):
        raise ScriptGenerationError("Quiz options failed integrity validation.")


def _system_prompt() -> str:
    return (
        "You create German short-video quiz scripts as strict JSON. "
        "The quiz facts are immutable: question, options, correct answer, explanation, "
        "level, and topic must not be changed. Image prompts must describe scenes only "
        "and must never ask for text, letters, captions, questions, or answers inside images."
    )
