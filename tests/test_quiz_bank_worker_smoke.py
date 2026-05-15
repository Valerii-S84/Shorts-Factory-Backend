from __future__ import annotations

import json
from pathlib import Path

import httpx

from shorts_factory.db.models import Base, JobStatus, PublishPlatform
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.generation.schemas import FrameType, GeneratedScript, ScriptFrame
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
            hook="Kannst du das lösen?",
            voiceover=f"{quiz.question} Richtig ist {quiz.correct_option_label}.",
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

    def generate(self, *, job_id: int, script: GeneratedScript) -> Path:
        path = self._media_root / f"job-{job_id}" / "voice.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(script.voiceover.encode())
        return path


class SmokeRenderer:
    def render(self, render_plan: RenderPlan) -> str:
        path = Path(render_plan.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mp4")
        return str(path)


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


class SmokeTelegramPublisher:
    def publish_video(self, *, video_path: str, caption: str) -> PublishResult:
        return PublishResult(external_id="telegram-1", chat_id="-100", url="https://t.me/c/1")


def test_quiz_bank_item_to_render_and_publish_reports_delivery_outcome(tmp_path: Path) -> None:
    outcomes: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/quiz-items/next":
            return httpx.Response(
                200,
                json={"delivery_id": "delivery-1", "quiz_item": _quiz_bank_item_payload()},
            )
        if request.url.path == "/v1/deliveries/delivery-1/outcome":
            outcomes.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    settings = Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'smoke.db'}",
        media_root=tmp_path / "media",
        quiz_bank_base_url="https://api.valerchik.de",
        quiz_bank_edge_api_key="edge-token",
        quiz_bank_api_key="bank-token",
    )
    engine = create_database_engine(settings.effective_database_url)
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        repository = VideoJobRepository(session)
        job = repository.create(target_platforms=[PublishPlatform.TELEGRAM.value])
        worker = VideoJobWorker(
            settings=settings,
            repository=repository,
            quiz_bank_client=QuizBankClient(
                settings,
                http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            ),
            script_generator=SmokeScriptGenerator(),
            image_generator=SmokeImageGenerator(tmp_path),
            voice_generator=SmokeVoiceGenerator(tmp_path),
            renderer=SmokeRenderer(),
            qa_service=SmokeQAService(),
            publish_service=PublishService(repository, SmokeTelegramPublisher()),
            storage=LocalStorage(),
        )

        worker.run(job.id)

        completed_job = repository.get_with_children(job.id)
        assert completed_job.quiz_id == "item-1"
        assert completed_job.status == JobStatus.TELEGRAM_PUBLISHED.value
        assert completed_job.video_path is not None
        assert completed_job.render_plan_json["quiz_id"] == "item-1"
        assert outcomes == [{"outcome": "sent"}]
    finally:
        session.close()
        engine.dispose()


def _quiz_bank_item_payload() -> dict[str, object]:
    return {
        "id": "item-1",
        "question": "Welcher Artikel passt zu Brücke?",
        "options": [
            {"id": "option-der", "text": "der"},
            {"id": "option-die", "text": "die"},
            {"id": "option-das", "text": "das"},
        ],
        "feedback": {
            "correctAnswerId": "option-die",
            "explanation": "Brücke ist feminin: die Brücke.",
        },
        "level": "A1",
        "topic": "Artikel",
        "status": "approved",
    }
