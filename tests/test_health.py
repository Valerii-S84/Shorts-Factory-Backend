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


def test_ready_reports_missing_database_url() -> None:
    app = create_app(Settings(environment="test"))

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert {
        "name": "database_url",
        "status": "failed",
        "detail": "DATABASE_URL is not configured.",
    } in payload["checks"]


def test_ready_passes_with_configured_database_url_and_media_parent() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        media_root=".",
    )
    app = create_app(settings)

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
