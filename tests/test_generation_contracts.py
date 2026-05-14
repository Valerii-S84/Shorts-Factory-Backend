import pytest
from pydantic import ValidationError

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.generation.script_generator import (
    ScriptGenerationError,
    validate_script_preserves_quiz_facts,
)
from shorts_factory.quiz_bank.schemas import Quiz


def quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "quiz-1",
            "question": "Was bedeutet 'Haus'?",
            "options": [
                {"label": "A", "text": "house"},
                {"label": "B", "text": "car"},
            ],
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
            "hook": "Kannst du das lösen?",
            "voiceover": "Was bedeutet 'Haus'? Richtig ist A, house.",
            "frames": [
                {
                    "type": "hook",
                    "text": "Kannst du das lösen?",
                    "image_prompt": "German classroom, warm light, clean illustration",
                },
                {
                    "type": "question",
                    "text": "Was bedeutet 'Haus'?",
                    "image_prompt": "Student thinking in a German class, clean illustration",
                },
                {
                    "type": "options",
                    "text": "A house\nB car",
                    "image_prompt": "Quiz atmosphere in a German lesson, clean illustration",
                },
                {
                    "type": "answer",
                    "text": "Richtig ist: A house",
                    "image_prompt": "Happy student learning vocabulary, clean illustration",
                },
            ],
            "telegram_caption": "Deutsch Quiz",
            "youtube_title": "Deutsch Quiz",
            "youtube_description": "Deutsch Quiz",
        }
    )


def test_generated_script_preserves_quiz_question_and_answer() -> None:
    validate_script_preserves_quiz_facts(valid_script(), quiz())


def test_generated_script_rejects_image_prompt_text_instruction() -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"][0]["image_prompt"] = "draw text with answer options"

    with pytest.raises(ValidationError):
        GeneratedScript.model_validate(payload)


def test_generated_script_rejects_changed_question() -> None:
    script = valid_script()
    script.frames[1].text = "Was bedeutet 'Auto'?"

    with pytest.raises(ScriptGenerationError):
        validate_script_preserves_quiz_facts(script, quiz())
