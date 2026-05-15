from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from shorts_factory.api import health as health_module
from shorts_factory.api.health import create_health_router
from shorts_factory.main import create_app
from shorts_factory.settings import Settings


def test_health_reports_service_status() -> None:
    app = create_app(Settings(environment="test"))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Shorts Factory Backend",
        "environment": "test",
    }


def test_ready_reports_staging_missing_database_url(tmp_path: Path) -> None:
    app = create_app(Settings(environment="staging", media_root=tmp_path / "media"))

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert {
        "name": "database_url",
        "status": "failed",
        "detail": "DATABASE_URL is not configured.",
    } in payload["checks"]


def test_ready_passes_with_local_defaults() -> None:
    settings = Settings(
        environment="local",
        media_root="var/media",
    )
    app = create_app(settings)

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_reports_missing_ffmpeg(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        media_root=tmp_path / "media",
        ffmpeg_path="missing-ffmpeg-binary",
    )
    app = create_app(settings)

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert {
        "name": "ffmpeg",
        "status": "failed",
        "detail": "Executable is not available: missing-ffmpeg-binary",
    } in response.json()["checks"]


def test_ready_reports_database_exception(monkeypatch, tmp_path: Path) -> None:
    def raise_database_error(database_url: str):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(health_module, "create_database_engine", raise_database_error)
    app = _health_app(
        Settings(
            environment="staging",
            database_url="sqlite+pysqlite:///unreachable.db",
            media_root=tmp_path,
        )
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert {
        "name": "database_url",
        "status": "failed",
        "detail": "Database is not reachable.",
    } in response.json()["checks"]


def test_ready_reports_media_root_is_not_directory(tmp_path: Path) -> None:
    media_root = tmp_path / "media-file"
    media_root.write_text("not a directory")
    app = _health_app(
        Settings(
            environment="staging",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
            media_root=media_root,
        )
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert {
        "name": "media_root",
        "status": "failed",
        "detail": f"Media root is not a directory: {media_root}",
    } in response.json()["checks"]


def test_ready_reports_missing_media_root(tmp_path: Path) -> None:
    media_root = tmp_path / "missing-media"
    app = _health_app(
        Settings(
            environment="staging",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
            media_root=media_root,
        )
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert {
        "name": "media_root",
        "status": "failed",
        "detail": f"Media root does not exist: {media_root}",
    } in response.json()["checks"]


def _health_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.include_router(create_health_router(settings))
    return app
