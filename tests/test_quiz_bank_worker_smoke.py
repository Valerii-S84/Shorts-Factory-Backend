from __future__ import annotations

from pathlib import Path

from shorts_factory.db.models import JobStatus, PublishPlatform
from tests.worker_smoke_support import (
    SmokeQAService,
    SmokeRenderer,
    SmokeTelegramPublisher,
    build_worker,
    create_repository,
    quiz_bank_handler,
    smoke_settings,
)


def test_quiz_bank_item_to_render_and_publish_reports_delivery_outcome(tmp_path: Path) -> None:
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
            qa_service=SmokeQAService(),
            publisher=publisher,
        )

        worker.run(job.id)

        completed_job = repository.get_with_children(job.id)
        audio_asset = next(asset for asset in completed_job.assets if asset.type == "audio")

        assert completed_job.quiz_id == "item-1"
        assert completed_job.status == JobStatus.DONE.value
        assert completed_job.finished_at is not None
        assert completed_job.video_path is not None
        assert completed_job.render_plan_json["quiz_id"] == "item-1"
        assert completed_job.render_plan_json["creative_metadata"]["template_id"] == "grammar_trap"
        assert audio_asset.path.endswith("voiceover.mp3")
        assert audio_asset.metadata_json["audio_checksum"] == audio_asset.checksum
        assert completed_job.publish_logs[0].metadata_json["platform"] == "telegram"
        assert completed_job.publish_logs[0].metadata_json["publish_url"] == "https://t.me/c/1"
        assert publisher.calls == 1
        assert outcomes == [{"status": "sent"}]
    finally:
        session.close()
        engine.dispose()
