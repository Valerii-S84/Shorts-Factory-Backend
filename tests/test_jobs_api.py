from fastapi.testclient import TestClient

from shorts_factory.main import create_app
from shorts_factory.settings import Settings


def test_jobs_api_requires_api_key(tmp_path) -> None:
    app = create_app(
        Settings(
            environment="test",
            api_key="secret",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
            media_root=tmp_path / "media",
        )
    )

    response = TestClient(app).post("/jobs/create", json={})

    assert response.status_code == 401


def test_jobs_api_creates_manual_job(tmp_path) -> None:
    app = create_app(
        Settings(
            environment="test",
            api_key="secret",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
            media_root=tmp_path / "media",
        )
    )

    response = TestClient(app).post(
        "/jobs/create",
        headers={"X-API-Key": "secret"},
        json={"quiz_id": "quiz-1", "target_platforms": ["telegram"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["quiz_id"] == "quiz-1"
    assert payload["status"] == "created"
