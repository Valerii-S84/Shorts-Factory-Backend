from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from shorts_factory.db.models import RecordStatus
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_session_factory, get_engine
from shorts_factory.dev.offline_providers import (
    FFmpegPlaceholderImageGenerator,
    FFmpegPlaceholderVoiceGenerator,
    OfflineQuizBankClient,
    OfflineScriptGenerator,
    OfflineTelegramPublisher,
)
from shorts_factory.jobs.worker import VideoJobWorker
from shorts_factory.publishing.publish_service import PublishService
from shorts_factory.rendering.ffmpeg_renderer import FFmpegRenderer
from shorts_factory.rendering.qa_probe import FFprobeVideoProbe, VideoQAService
from shorts_factory.runtime import prepare_local_database, prepare_runtime_paths
from shorts_factory.settings import Settings
from shorts_factory.storage.local_storage import LocalStorage


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = Settings(
        environment=args.environment,
        database_url=args.database_url,
        media_root=args.media_root,
        ffmpeg_path=args.ffmpeg_path,
        ffprobe_path=args.ffprobe_path,
    )
    summary = run_local_e2e(settings)
    print(_format_summary(summary))
    return 0


def run_local_e2e(settings: Settings) -> dict[str, object]:
    prepare_runtime_paths(settings)
    prepare_local_database(settings)

    engine = get_engine(settings)
    if engine is None:
        raise RuntimeError("Database is not configured for local E2E.")

    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        repository = VideoJobRepository(session)
        job = repository.create(target_platforms=[])
        worker = _worker(settings, repository)
        worker.run(job.id)

        repository.add_render_log(
            job,
            step="offline_e2e",
            status=RecordStatus.SUCCESS,
            message="Local offline E2E created a QA-passed MP4 without publishing.",
        )
        session.commit()
        session.expire_all()
        completed_job = repository.get_with_children(job.id)
        return {
            "job_id": completed_job.id,
            "status": completed_job.status,
            "quiz_id": completed_job.quiz_id,
            "video_path": completed_job.video_path,
            "duration_sec": completed_job.duration_sec,
            "assets": len(completed_job.assets),
            "render_logs": len(completed_job.render_logs),
            "database_url": settings.effective_database_url,
            "media_root": str(settings.media_root),
        }
    finally:
        session.close()
        engine.dispose()


def _worker(settings: Settings, repository: VideoJobRepository) -> VideoJobWorker:
    storage = LocalStorage()
    return VideoJobWorker(
        settings=settings,
        repository=repository,
        quiz_bank_client=OfflineQuizBankClient(),
        script_generator=OfflineScriptGenerator(),
        image_generator=FFmpegPlaceholderImageGenerator(settings),
        voice_generator=FFmpegPlaceholderVoiceGenerator(settings),
        renderer=FFmpegRenderer(settings),
        qa_service=VideoQAService(FFprobeVideoProbe(settings)),
        publish_service=PublishService(repository, OfflineTelegramPublisher()),
        storage=storage,
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local offline quiz-to-MP4 E2E without external API calls."
    )
    parser.add_argument(
        "--environment",
        choices=["local", "development", "test"],
        default="local",
        help="Non-production environment for the local E2E run.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLite SQLAlchemy URL. Defaults to local settings.",
    )
    parser.add_argument(
        "--media-root",
        type=Path,
        default=Path("var/media"),
        help="Directory for generated local media assets.",
    )
    parser.add_argument("--ffmpeg-path", default="ffmpeg", help="Path to the ffmpeg binary.")
    parser.add_argument("--ffprobe-path", default="ffprobe", help="Path to the ffprobe binary.")
    return parser.parse_args(argv)


def _format_summary(summary: dict[str, object]) -> str:
    lines = ["Local offline E2E completed:"]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
