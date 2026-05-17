from __future__ import annotations

import json
from pathlib import Path

import httpx

from shorts_factory.db.models import Base
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.generation.schemas import FrameType, GeneratedScript, ScriptFrame
from shorts_factory.generation.voice_generator import GeneratedVoiceover
from shorts_factory.generation.voiceover_script import VoiceoverPlan
from shorts_factory.jobs.worker import VideoJobWorker
from shorts_factory.publishing.publish_service import PublishService
from shorts_factory.publishing.telegram_publisher import PublishResult
from shorts_factory.quiz_bank.client import QuizBankClient
from shorts_factory.quiz_bank.schemas import Quiz
from shorts_factory.rendering.qa_probe import QAResult, VideoProbe
from shorts_factory.rendering.render_plan import RenderPlan
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


class SmokeScriptGenerator:
    def generate(self, quiz: Quiz) -> GeneratedScript:
        return GeneratedScript(
            frames=[
                ScriptFrame(
                    type=FrameType.QUESTION,
                    text=quiz.question,
                    image_prompt="Student at a bright desk",
                ),
                ScriptFrame(
                    type=FrameType.OPTIONS,
                    text="\n".join(f"{option.label} {option.text}" for option in quiz.options),
                    image_prompt="Learning cards on a table",
                ),
                ScriptFrame(
                    type=FrameType.ANSWER,
                    text=f"Richtig ist: {quiz.correct_option_label} {quiz.correct_option.text}",
                    image_prompt="Happy learner in a classroom",
                ),
            ],
            telegram_caption=f"Deutsch-Quiz: {quiz.topic}",
            youtube_title=f"Deutsch-Quiz: {quiz.topic}",
            youtube_description=quiz.explanation,
        )


class SmokeImageGenerator:
    def __init__(self, media_root: Path) -> None:
        self._media_root = media_root

    def generate(self, *, job_id: int, script: GeneratedScript) -> list[Path]:
        paths = []
        for index, _frame in enumerate(script.frames, start=1):
            path = self._media_root / f"job-{job_id}" / f"frame-{index}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"image")
            paths.append(path)
        return paths


class SmokeVoiceGenerator:
    def __init__(self, media_root: Path) -> None:
        self._media_root = media_root

    def generate(self, *, job_id: int, voiceover_plan: VoiceoverPlan) -> GeneratedVoiceover:
        path = self._media_root / f"job-{job_id}" / "voiceover.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(voiceover_plan.text.encode())
        return GeneratedVoiceover(path, "gpt-4o-mini-tts", "cedar", 0.8, "mp3")


class SmokeRenderer:
    def render(self, render_plan: RenderPlan) -> str:
        path = Path(render_plan.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mp4")
        return str(path)


class FailingRenderer:
    def render(self, render_plan: RenderPlan) -> str:
        raise RuntimeError("render failed while building mp4")


class SmokeQAService:
    def validate(self, *, video_path: str, quiz: Quiz, render_plan: RenderPlan) -> QAResult:
        return QAResult(
            passed=True,
            probe=VideoProbe(
                path=video_path,
                width=1080,
                height=1920,
                duration_sec=render_plan.duration_sec,
                has_audio=True,
            ),
        )


class FailingAudioQAService:
    def validate(self, *, video_path: str, quiz: Quiz, render_plan: RenderPlan) -> QAResult:
        raise RuntimeError("Audio file is empty.")


class SmokeTelegramPublisher:
    def __init__(self) -> None:
        self.calls = 0

    def publish_video(self, *, video_path: str, caption: str) -> PublishResult:
        self.calls += 1
        return PublishResult(external_id="telegram-1", chat_id="-100", url="https://t.me/c/1")


def smoke_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'smoke.db'}",
        media_root=tmp_path / "media",
        quiz_bank_base_url="https://api.valerchik.de",
        quiz_bank_edge_api_key="edge-token",
        quiz_bank_api_key="bank-token",
    )


def quiz_bank_handler(outcomes: list[dict[str, str]]):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/quiz-items/next":
            return httpx.Response(
                200,
                json={"delivery_id": "delivery-1", "quiz_item": quiz_bank_item_payload()},
            )
        if request.url.path == "/v1/deliveries/delivery-1/outcome":
            outcomes.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    return handler


def create_repository(settings: Settings):
    engine = create_database_engine(settings.effective_database_url)
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    return engine, session, VideoJobRepository(session)


def build_worker(
    *,
    settings: Settings,
    repository: VideoJobRepository,
    handler,
    media_root: Path,
    renderer,
    qa_service,
    publisher,
) -> VideoJobWorker:
    return VideoJobWorker(
        settings=settings,
        repository=repository,
        quiz_bank_client=QuizBankClient(
            settings,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
        script_generator=SmokeScriptGenerator(),
        image_generator=SmokeImageGenerator(media_root),
        voice_generator=SmokeVoiceGenerator(media_root),
        renderer=renderer,
        qa_service=qa_service,
        publish_service=PublishService(repository, publisher),
        storage=LocalStorage(),
    )


def quiz_bank_item_payload() -> dict[str, object]:
    return {
        "id": "item-1",
        "question": "Welcher Artikel passt zu Brücke?",
        "options": [
            {"id": "option-der", "text": "der"},
            {"id": "option-die", "text": "die"},
            {"id": "option-das", "text": "das"},
        ],
        "feedback": {"correctAnswerId": "option-die", "explanation": "Brücke ist feminin."},
        "level": "A1",
        "topic": "Artikel",
        "status": "approved",
    }
