from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shorts_factory.db.models import AssetType, Base, JobStatus
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.jobs.scheduler import create_manual_job
from shorts_factory.main import create_app
from shorts_factory.settings import Settings

API_HEADERS = {"X-API-Key": "secret"}


def test_jobs_api_requires_api_key(tmp_path: Path) -> None:
    response = _client(tmp_path).post("/jobs/create", json={})

    assert response.status_code == 401


def test_jobs_api_returns_503_when_api_key_not_configured(tmp_path: Path) -> None:
    response = _client(tmp_path, api_key=None).post("/jobs/create", headers=API_HEADERS, json={})

    assert response.status_code == 503
    assert response.json()["detail"] == "SHORTS_FACTORY_API_KEY is not configured."


def test_jobs_api_returns_503_when_database_not_configured(tmp_path: Path) -> None:
    app = create_app(Settings(environment="staging", api_key="secret", media_root=tmp_path))

    response = TestClient(app).post("/jobs/create", headers=API_HEADERS, json={})

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not configured."


def test_jobs_api_creates_manual_job(tmp_path: Path) -> None:
    response = _post_create(_client(tmp_path))

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["quiz_id"] == "quiz-1"
    assert payload["status"] == "created"


def test_jobs_api_lists_jobs(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _create_job(client, quiz_id="quiz-1")
    _create_job(client, quiz_id="quiz-2", platform="youtube")

    response = client.get("/jobs", headers=API_HEADERS)

    assert response.status_code == 200
    assert [job["quiz_id"] for job in response.json()] == ["quiz-2", "quiz-1"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/jobs/404"),
        ("get", "/jobs/404/assets"),
        ("post", "/jobs/404/retry"),
        ("post", "/jobs/404/publish/telegram"),
        ("post", "/jobs/404/publish/youtube"),
    ],
)
def test_jobs_api_returns_404_for_missing_job(tmp_path: Path, method: str, path: str) -> None:
    response = getattr(_client(tmp_path), method)(path, headers=API_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "Video job does not exist: 404"


def test_jobs_api_returns_job(tmp_path: Path) -> None:
    client = _client(tmp_path)
    job_id = _create_job(client)

    response = client.get(f"/jobs/{job_id}", headers=API_HEADERS)

    assert response.status_code == 200
    assert response.json()["quiz_id"] == "quiz-1"


def test_jobs_api_returns_assets(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    job_id = _create_job_with_asset(settings.database_url)

    response = TestClient(app).get(f"/jobs/{job_id}/assets", headers=API_HEADERS)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "type": "image",
            "path": "images/quiz-1.png",
            "checksum": "sha256:asset",
            "metadata_json": {"frame": 1},
        }
    ]


def test_jobs_api_retries_job(tmp_path: Path) -> None:
    client = _client(tmp_path)
    job_id = _create_job(client)

    response = client.post(f"/jobs/{job_id}/retry", headers=API_HEADERS)

    assert response.status_code == 200
    assert response.json()["retry_count"] == 1
    assert response.json()["status"] == "retry_pending"


def test_manual_job_creation_does_not_retry_existing_failed_job(tmp_path: Path) -> None:
    repository, session, engine = _repository(_settings(tmp_path).database_url)
    Base.metadata.create_all(engine)
    try:
        failed_job = repository.create(quiz_id="old-quiz", target_platforms=[])
        failed_job.retry_count = 3
        repository.update_status(
            failed_job,
            JobStatus.FAILED,
            error_message="old render failed",
            finished=True,
        )

        new_job_id = create_manual_job(repository, quiz_id="new-quiz", target_platforms=[])

        session.flush()
        assert new_job_id != failed_job.id
        assert failed_job.status == JobStatus.FAILED.value
        assert failed_job.retry_count == 3
        assert repository.get(new_job_id).status == JobStatus.CREATED.value
    finally:
        session.close()
        engine.dispose()


def test_jobs_api_publish_telegram_conflict_without_config(tmp_path: Path) -> None:
    client = _client(tmp_path)
    job_id = _create_job(client)

    response = client.post(f"/jobs/{job_id}/publish/telegram", headers=API_HEADERS)

    assert response.status_code == 409
    assert response.json()["detail"] == "TELEGRAM_BOT_TOKEN is not configured."


def test_jobs_api_exposes_youtube_publish_endpoint_without_real_call(tmp_path: Path) -> None:
    client = _client(tmp_path, youtube_access_token="token")
    job_id = _create_job(client, platform="youtube")

    response = client.post(f"/jobs/{job_id}/publish/youtube", headers=API_HEADERS)

    assert response.status_code == 409
    assert response.json()["status"] == "created"


def _settings(tmp_path: Path, **overrides: str | None) -> Settings:
    values = {
        "environment": "test",
        "api_key": "secret",
        "database_url": f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        "media_root": tmp_path / "media",
    }
    values.update(overrides)
    return Settings(**values)


def _client(tmp_path: Path, **settings_overrides: str | None) -> TestClient:
    return TestClient(create_app(_settings(tmp_path, **settings_overrides)))


def _post_create(client: TestClient, *, quiz_id: str = "quiz-1", platform: str = "telegram"):
    return client.post(
        "/jobs/create",
        headers=API_HEADERS,
        json={"quiz_id": quiz_id, "target_platforms": [platform]},
    )


def _create_job(client: TestClient, *, quiz_id: str = "quiz-1", platform: str = "telegram") -> int:
    response = _post_create(client, quiz_id=quiz_id, platform=platform)
    assert response.status_code == 200
    return response.json()["id"]


def _create_job_with_asset(database_url: str | None) -> int:
    repository, session, engine = _repository(database_url)
    try:
        job = repository.create(quiz_id="quiz-1")
        repository.add_asset(
            job,
            asset_type=AssetType.IMAGE,
            path="images/quiz-1.png",
            checksum="sha256:asset",
            metadata={"frame": 1},
        )
        session.commit()
        return job.id
    finally:
        session.close()
        engine.dispose()


def _repository(database_url: str | None):
    if database_url is None:
        raise AssertionError("Test database URL must be configured.")
    engine = create_database_engine(database_url)
    session = create_session_factory(engine)()
    return VideoJobRepository(session), session, engine
