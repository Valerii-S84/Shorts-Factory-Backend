import pytest
from pydantic import ValidationError

from shorts_factory.generation.image_prompt_builder import ImagePromptBuilder
from shorts_factory.generation.image_style_contract import PRODUCTION_IMAGE_STYLE_CONTRACT
from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.generation.script_generator import (
    ScriptGenerationError,
    _system_prompt,
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
            "voiceover": "Was bedeutet 'Haus'? Optionen: A house, B car. Richtig ist A, house.",
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


def test_generated_script_preserves_quiz_question_and_answer() -> None:
    validate_script_preserves_quiz_facts(valid_script(), quiz())


def test_generated_script_uses_three_frames_without_legacy_required_segments() -> None:
    script = valid_script()

    assert [frame.type.value for frame in script.frames] == ["question", "options", "answer"]
    assert not hasattr(script, "hook")
    assert {frame.type.value for frame in script.frames}.isdisjoint({"hook", "pause", "cta"})


def test_generated_script_rejects_image_prompt_text_instruction() -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"][0]["image_prompt"] = "draw text with answer options"

    with pytest.raises(ValidationError):
        GeneratedScript.model_validate(payload)


@pytest.mark.parametrize(
    "forbidden_prompt",
    [
        "draw text on the wall",
        "floating letters above the desk",
        "add a caption at the bottom",
        "show answer options on cards",
        "deutsche Schrift an der Tafel",
        "show question text above the student",
        "small labels on learning cards",
        "UI panel in the corner",
        "school logo on the notebook",
        "subtle watermark near the bottom",
    ],
)
def test_generated_script_blocks_standalone_visible_text_concepts(
    forbidden_prompt: str,
) -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"][0]["image_prompt"] = forbidden_prompt

    with pytest.raises(ValidationError):
        GeneratedScript.model_validate(payload)


@pytest.mark.parametrize(
    "allowed_prompt",
    [
        "wood texture on a classroom desk",
        "textured wooden desk beside a window",
        "historical context shown through classroom objects",
    ],
)
def test_generated_script_allows_non_forbidden_text_substrings(
    allowed_prompt: str,
) -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"][0]["image_prompt"] = allowed_prompt

    script = GeneratedScript.model_validate(payload)

    assert script.frames[0].image_prompt == allowed_prompt


def test_generated_script_rejects_old_six_frame_production_script() -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"] = [
        {"type": "hook", "text": "Hook", "image_prompt": "Curious student"},
        *payload["frames"][:2],
        {"type": "pause", "text": "3\n2\n1", "image_prompt": "Thinking student"},
        payload["frames"][2],
        {"type": "cta", "text": "Follow", "image_prompt": "Study desk"},
    ]

    with pytest.raises(ValidationError):
        GeneratedScript.model_validate(payload)


def test_generated_script_rejects_more_than_three_frames() -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"].append(payload["frames"][0])

    with pytest.raises(ValidationError):
        GeneratedScript.model_validate(payload)


@pytest.mark.parametrize(
    "missing_index",
    [
        pytest.param(0, id="missing-question"),
        pytest.param(1, id="missing-options"),
        pytest.param(2, id="missing-answer"),
    ],
)
def test_generated_script_rejects_missing_required_production_frame(missing_index: int) -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"].pop(missing_index)

    with pytest.raises(ValidationError):
        GeneratedScript.model_validate(payload)


@pytest.mark.parametrize(
    "frame_order",
    [
        pytest.param([2, 0, 1], id="answer-question-options"),
        pytest.param([0, 2, 1], id="question-answer-options"),
        pytest.param([1, 0, 2], id="options-question-answer"),
    ],
)
def test_generated_script_rejects_invalid_production_frame_order(frame_order: list[int]) -> None:
    payload = valid_script().model_dump(mode="json")
    payload["frames"] = [payload["frames"][index] for index in frame_order]

    with pytest.raises(ValidationError, match="question -> options -> answer"):
        GeneratedScript.model_validate(payload)


def test_image_prompt_builder_includes_style_contract_and_rules() -> None:
    prompt = ImagePromptBuilder().build("Student thinking beside a window")

    assert PRODUCTION_IMAGE_STYLE_CONTRACT in prompt
    assert "Student thinking beside a window" in prompt
    assert "no visible text" in prompt
    assert "main subject centered in upper/middle area" in prompt
    assert "lower third visually calm for backend overlay" in prompt


def test_image_prompt_builder_strips_scene_brief_whitespace() -> None:
    prompt = ImagePromptBuilder().build("  Student thinking beside a window  ")

    assert "Scene brief:\nStudent thinking beside a window\n\nNegative rules:" in prompt


def test_image_prompt_builder_rejects_blank_scene_brief() -> None:
    with pytest.raises(ValueError, match="scene brief"):
        ImagePromptBuilder().build("   ")


def test_script_system_prompt_defines_image_prompt_as_scene_brief() -> None:
    prompt = _system_prompt()

    assert "frame.image_prompt is only" in prompt
    assert "scene brief, not a full style prompt" in prompt
    assert "exactly three frames" in prompt
    assert "question, options, answer" in prompt
    assert "Do not create a hook" in prompt
    assert "speech speed 0.8" in prompt
    assert "read the question" in prompt
    assert "read the options" in prompt
    assert "reveal the correct answer" in prompt
    assert "facts are immutable" in prompt
    assert "question text" in prompt
    assert "answer options" in prompt
    assert "logos" in prompt
    assert "watermarks" in prompt


def test_generated_script_rejects_changed_question() -> None:
    script = valid_script()
    script.frames[0].text = "Was bedeutet 'Auto'?"

    with pytest.raises(ScriptGenerationError):
        validate_script_preserves_quiz_facts(script, quiz())
