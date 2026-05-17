from __future__ import annotations

from pathlib import Path

import pytest

from shorts_factory.db.models import RecordStatus
from shorts_factory.dev import local_e2e, offline_providers
from shorts_factory.dev.offline_providers import (
    FFmpegPlaceholderImageGenerator,
    FFmpegPlaceholderVoiceGenerator,
    OfflineQuizBankClient,
    OfflineScriptGenerator,
    OfflineTelegramPublisher,
)
from shorts_factory.generation.voiceover_script import build_voiceover_plan
from shorts_factory.settings import Settings


def test_main_formats_local_e2e_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        local_e2e,
        "run_local_e2e",
        lambda settings: {"job_id": 7, "media_root": str(settings.media_root)},
    )

    exit_code = local_e2e.main(["--environment", "test", "--media-root", str(tmp_path)])

    assert exit_code == 0
    assert "Local offline E2E completed:" in capsys.readouterr().out


def test_run_local_e2e_uses_offline_worker_without_publishing(monkeypatch, tmp_path: Path) -> None:
    fake_engine = FakeEngine()
    fake_session = FakeSession()
    fake_worker = FakeWorker()
    monkeypatch.setattr(local_e2e, "prepare_runtime_paths", lambda settings: None)
    monkeypatch.setattr(local_e2e, "prepare_local_database", lambda settings: None)
    monkeypatch.setattr(local_e2e, "get_engine", lambda settings: fake_engine)
    monkeypatch.setattr(local_e2e, "create_session_factory", lambda engine: lambda: fake_session)
    monkeypatch.setattr(local_e2e, "VideoJobRepository", FakeRepository)
    monkeypatch.setattr(local_e2e, "_worker", lambda settings, repository: fake_worker)

    summary = local_e2e.run_local_e2e(settings(tmp_path))

    assert summary["job_id"] == 101
    assert summary["status"] == "qa_passed"
    assert summary["assets"] == 2
    assert fake_worker.ran_job_id == 101
    assert fake_session.committed
    assert fake_session.closed
    assert fake_engine.disposed
    assert FakeRepository.last_log["status"] == RecordStatus.SUCCESS


def test_run_local_e2e_rejects_missing_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(local_e2e, "prepare_runtime_paths", lambda settings: None)
    monkeypatch.setattr(local_e2e, "prepare_local_database", lambda settings: None)
    monkeypatch.setattr(local_e2e, "get_engine", lambda settings: None)

    with pytest.raises(RuntimeError, match="Database is not configured"):
        local_e2e.run_local_e2e(settings(tmp_path))


def test_offline_providers_build_assets_with_configured_paths(monkeypatch, tmp_path: Path) -> None:
    commands = []

    def fake_run(command: list[str]) -> None:
        commands.append(command)
        Path(command[-1]).write_bytes(b"asset")

    monkeypatch.setattr(offline_providers, "_run_command", fake_run)
    source_quiz = OfflineQuizBankClient().fetch_next_approved_quiz()
    script = OfflineScriptGenerator().generate(source_quiz)
    app_settings = settings(tmp_path)

    image_paths = FFmpegPlaceholderImageGenerator(app_settings).generate(job_id=5, script=script)
    voiceover = FFmpegPlaceholderVoiceGenerator(app_settings).generate(
        job_id=5,
        voiceover_plan=build_voiceover_plan(source_quiz),
    )

    assert len(image_paths) == 3
    assert all(path.read_bytes() == b"asset" for path in image_paths)
    assert voiceover.path == tmp_path / "audio" / "5" / "voiceover.mp3"
    assert voiceover.path.read_bytes() == b"asset"
    assert len(commands) == 4


def test_offline_quiz_and_publisher_fail_safely() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        OfflineQuizBankClient().fetch_quiz("missing")

    with pytest.raises(RuntimeError, match="disables Telegram"):
        OfflineTelegramPublisher().publish_video(video_path="short.mp4", caption="caption")


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def expire_all(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class FakeWorker:
    def __init__(self) -> None:
        self.ran_job_id: int | None = None

    def run(self, job_id: int) -> None:
        self.ran_job_id = job_id


class FakeRepository:
    last_log: dict[str, object] = {}

    def __init__(self, session: FakeSession) -> None:
        self._job = FakeJob()

    def create(self, *, target_platforms: list[str]) -> FakeJob:
        assert target_platforms == []
        return self._job

    def add_render_log(self, job: FakeJob, **kwargs) -> None:
        FakeRepository.last_log = kwargs

    def get_with_children(self, job_id: int) -> FakeJob:
        return self._job


class FakeJob:
    id = 101
    status = "qa_passed"
    quiz_id = "offline-quiz"
    video_path = "short.mp4"
    duration_sec = 15.5
    assets = [object(), object()]
    render_logs = [object()]


def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        media_root=tmp_path,
    )
