from pathlib import Path

from fastapi.testclient import TestClient

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
