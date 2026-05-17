from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_factory.generation.metadata_generator import (
    telegram_caption,
    youtube_description,
    youtube_title,
)
from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.generation.script_generator import OpenAIScriptGenerator, ScriptGenerationError
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings


def test_openai_script_generator_returns_validated_script() -> None:
    client = FakeScriptClient(valid_script())
    generator = OpenAIScriptGenerator(_settings(), client=client)

    script = generator.generate(quiz())

    assert script.youtube_title == "Deutsch Quiz"
    assert client.calls[0]["model"] == "gpt-test"
    assert client.calls[0]["text_format"] is GeneratedScript


def test_openai_script_generator_requires_api_key() -> None:
    with pytest.raises(ScriptGenerationError, match="OPENAI_API_KEY"):
        OpenAIScriptGenerator(Settings(environment="test"))


def test_openai_script_generator_rejects_empty_parsed_response() -> None:
    generator = OpenAIScriptGenerator(_settings(), client=FakeScriptClient(None))

    with pytest.raises(ScriptGenerationError, match="parsed script"):
        generator.generate(quiz())


def test_script_fact_validation_rejects_missing_correct_answer() -> None:
    script = valid_script()
    script.frames[-1].text = "Richtig ist: B car"

    with pytest.raises(ScriptGenerationError, match="correct answer"):
        OpenAIScriptGenerator(_settings(), client=FakeScriptClient(script)).generate(quiz())


def test_metadata_helpers_strip_script_metadata() -> None:
    script = valid_script()
    script.telegram_caption = " Telegram "
    script.youtube_title = " YouTube "
    script.youtube_description = " Beschreibung "

    assert telegram_caption(script) == "Telegram"
    assert youtube_title(script) == "YouTube"
    assert youtube_description(script) == "Beschreibung"


class FakeScriptClient:
    def __init__(self, parsed: GeneratedScript | None) -> None:
        self.calls = []
        self.responses = SimpleNamespace(parse=self.parse)
        self._parsed = parsed

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self._parsed)


def _settings(media_root: Path | None = None) -> Settings:
    return Settings(
        environment="test",
        media_root=media_root or Path("var/media"),
        openai_api_key="key",
        openai_script_model="gpt-test",
        openai_tts_model="tts-test",
    )


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-1",
            "question": "Was bedeutet 'Haus'?",
            "options": [{"label": "A", "text": "house"}, {"label": "B", "text": "car"}],
            "correct_answer": "A",
            "explanation": "Haus bedeutet house.",
            "level": "A1",
            "topic": "Vocabulary",
            "status": "published",
        }
    )


def valid_script() -> GeneratedScript:
    return GeneratedScript.model_validate(
        {
            "frames": [
                {
                    "type": "question",
                    "text": "Was bedeutet 'Haus'?",
                    "image_prompt": "Student thinking in a German class",
                },
                {
                    "type": "options",
                    "text": "A house\nB car",
                    "image_prompt": "Learning cards on a classroom table",
                },
                {
                    "type": "answer",
                    "text": "Richtig ist: A house",
                    "image_prompt": "Happy student learning vocabulary",
                },
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )
