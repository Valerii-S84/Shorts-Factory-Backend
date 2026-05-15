from __future__ import annotations

import subprocess
from pathlib import Path

from shorts_factory.generation.schemas import FrameType, GeneratedScript, ScriptFrame
from shorts_factory.generation.script_generator import validate_script_preserves_quiz_facts
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.settings import Settings
from shorts_factory.storage.asset_paths import job_asset_path

PLACEHOLDER_AUDIO_SECONDS = 18
PLACEHOLDER_COLORS = (
    "0x1f2937",
    "0x0f766e",
    "0x7c2d12",
    "0x1d4ed8",
    "0x4d7c0f",
    "0x6d28d9",
)


class OfflineAssetGenerationError(RuntimeError):
    pass


class OfflineQuizBankClient:
    def fetch_next_approved_quiz(self) -> Quiz:
        return _sample_quiz()

    def fetch_quiz(self, quiz_id: str) -> Quiz:
        quiz = _sample_quiz()
        if quiz_id != quiz.quiz_id:
            raise ValueError(f"Offline quiz fixture does not exist: {quiz_id}")
        return quiz


class OfflineScriptGenerator:
    def generate(self, quiz: Quiz) -> GeneratedScript:
        script = GeneratedScript(
            hook="Der, die oder das?",
            voiceover=_voiceover(quiz),
            frames=_script_frames(quiz),
            telegram_caption=f"Deutsch-Quiz: {quiz.topic} ({quiz.level})",
            youtube_title=f"Deutsch-Quiz: {quiz.topic}",
            youtube_description=quiz.explanation,
        )
        validate_script_preserves_quiz_facts(script, quiz)
        return script


class FFmpegPlaceholderImageGenerator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, *, job_id: int, script: GeneratedScript) -> list[Path]:
        image_paths = []
        for index, _frame in enumerate(script.frames, start=1):
            image_path = job_asset_path(self._settings, job_id, "images", f"frame_{index:02d}.png")
            image_path.parent.mkdir(parents=True, exist_ok=True)
            _run_command(_placeholder_image_command(self._settings, image_path, index))
            image_paths.append(image_path)
        return image_paths


class FFmpegPlaceholderVoiceGenerator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, *, job_id: int, script: GeneratedScript) -> Path:
        audio_path = job_asset_path(self._settings, job_id, "audio", "voiceover.wav")
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        _run_command(_placeholder_audio_command(self._settings, audio_path))
        return audio_path


class OfflineTelegramPublisher:
    def publish_video(self, *, video_path: str, caption: str) -> None:
        raise RuntimeError("Offline E2E disables Telegram publishing.")


def _sample_quiz() -> Quiz:
    return Quiz.model_validate(
        {
            "id": "offline-quiz-article-bruecke",
            "question": "Welcher Artikel passt zu Brücke?",
            "options": [
                {"label": "A", "text": "die"},
                {"label": "B", "text": "der"},
                {"label": "C", "text": "das"},
            ],
            "correct_answer": "A",
            "explanation": "Brücke ist feminin: die Brücke.",
            "level": "A1",
            "topic": "Artikel",
            "status": "approved",
        }
    )


def _voiceover(quiz: Quiz) -> str:
    options = ", ".join(f"{option.label}: {option.text}" for option in quiz.options)
    return (
        f"Der, die oder das? {quiz.question} {options}. Denk kurz nach. "
        f"Richtig ist {quiz.correct_option_label}: {quiz.correct_option.text}. "
        f"{quiz.explanation} Mehr Deutsch-Quiz im Telegram-Kanal."
    )


def _script_frames(quiz: Quiz) -> list[ScriptFrame]:
    options_text = "\n".join(f"{option.label} {option.text}" for option in quiz.options)
    return [
        ScriptFrame(
            type=FrameType.HOOK,
            text="Der, die oder das?",
            image_prompt="Bright study room with pencils and a notebook",
        ),
        ScriptFrame(
            type=FrameType.QUESTION,
            text=quiz.question,
            image_prompt="Student thinking at a desk in warm daylight",
        ),
        ScriptFrame(
            type=FrameType.OPTIONS,
            text=options_text,
            image_prompt="Three colorful learning cards on a table",
        ),
        ScriptFrame(
            type=FrameType.PAUSE,
            text="3\n2\n1",
            image_prompt="Student concentrating before choosing an answer",
        ),
        ScriptFrame(
            type=FrameType.ANSWER,
            text=f"Richtig: {quiz.correct_option_label} {quiz.correct_option.text}",
            image_prompt="Happy learner beside a small bridge model",
        ),
        ScriptFrame(
            type=FrameType.CTA,
            text="Mehr Deutsch-Quiz im Telegram-Kanal",
            image_prompt="Friendly learning desk with a smartphone nearby",
        ),
    ]


def _placeholder_image_command(settings: Settings, image_path: Path, index: int) -> list[str]:
    color = PLACEHOLDER_COLORS[(index - 1) % len(PLACEHOLDER_COLORS)]
    return [
        settings.ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=1080x1920:d=1",
        "-frames:v",
        "1",
        "-update",
        "1",
        str(image_path),
    ]


def _placeholder_audio_command(settings: Settings, audio_path: Path) -> list[str]:
    return [
        settings.ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=420:sample_rate=44100:duration={PLACEHOLDER_AUDIO_SECONDS}",
        "-filter:a",
        "volume=0.08",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]


def _run_command(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, check=False, text=True, timeout=60)
    if result.returncode != 0:
        message = result.stderr.strip() or "FFmpeg placeholder asset generation failed."
        raise OfflineAssetGenerationError(message)
