from __future__ import annotations

from pathlib import Path

import pytest

from shorts_factory.db.models import JobStatus, PublishPlatform
from tests.worker_smoke_support import (
    FailingAudioQAService,
    FailingRenderer,
    SmokeQAService,
    SmokeRenderer,
    SmokeTelegramPublisher,
    build_worker,
    create_repository,
    quiz_bank_handler,
    smoke_settings,
)


def test_worker_does_not_publish_to_telegram_when_audio_qa_fails(tmp_path: Path) -> None:
    outcomes: list[dict[str, str]] = []
    settings = smoke_settings(tmp_path)
    engine, session, repository = create_repository(settings)
    try:
        publisher = SmokeTelegramPublisher()
        job = repository.create(target_platforms=[PublishPlatform.TELEGRAM.value])
        worker = build_worker(
            settings=settings,
            repository=repository,
            handler=quiz_bank_handler(outcomes),
            media_root=tmp_path,
            renderer=SmokeRenderer(),
            qa_service=FailingAudioQAService(),
            publisher=publisher,
        )

        with pytest.raises(RuntimeError, match="Audio file is empty"):
            worker.run(job.id)

        completed_job = repository.get_with_children(job.id)
        assert completed_job.status == JobStatus.FAILED.value
        assert completed_job.publish_logs == []
        assert publisher.calls == 0
        assert outcomes == [{"status": "failed"}]
    finally:
        session.close()
        engine.dispose()


def test_worker_marks_recoverable_render_failure_retry_pending(tmp_path: Path) -> None:
    outcomes: list[dict[str, str]] = []
    settings = smoke_settings(tmp_path)
    engine, session, repository = create_repository(settings)
    try:
        job = repository.create(target_platforms=[PublishPlatform.TELEGRAM.value])
        worker = build_worker(
            settings=settings,
            repository=repository,
            handler=quiz_bank_handler(outcomes),
            media_root=tmp_path,
            renderer=FailingRenderer(),
            qa_service=SmokeQAService(),
            publisher=SmokeTelegramPublisher(),
        )

        with pytest.raises(RuntimeError, match="render failed"):
            worker.run(job.id)

        completed_job = repository.get_with_children(job.id)
        assert completed_job.status == JobStatus.RETRY_PENDING.value
        assert completed_job.error_message == "render failed while building mp4"
        assert completed_job.finished_at is None
        assert outcomes == [{"status": "failed"}]
    finally:
        session.close()
        engine.dispose()
