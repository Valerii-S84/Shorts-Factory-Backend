from __future__ import annotations

from shutil import which
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from shorts_factory.db.session import create_database_engine
from shorts_factory.settings import Settings


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str


class ReadinessCheck(BaseModel):
    name: str
    status: Literal["ok", "failed"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: list[ReadinessCheck]


def create_health_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            environment=settings.environment,
        )

    @router.get("/ready", response_model=ReadinessResponse)
    def ready(response: Response) -> ReadinessResponse:
        checks = _readiness_checks(settings)
        is_ready = all(check.status == "ok" for check in checks)
        if not is_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return ReadinessResponse(
            status="ready" if is_ready else "not_ready",
            checks=checks,
        )

    return router


def _readiness_checks(settings: Settings) -> list[ReadinessCheck]:
    checks = [
        ReadinessCheck(name="settings", status="ok"),
        _database_url_check(settings),
        _media_root_check(settings),
        _executable_check("ffmpeg", settings.ffmpeg_path),
        _executable_check("ffprobe", settings.ffprobe_path),
    ]
    return checks


def _database_url_check(settings: Settings) -> ReadinessCheck:
    database_url = settings.effective_database_url
    if database_url is None:
        return ReadinessCheck(
            name="database_url",
            status="failed",
            detail="DATABASE_URL is not configured.",
        )

    engine = None
    try:
        engine = create_database_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return ReadinessCheck(
            name="database_url",
            status="failed",
            detail="Database is not reachable.",
        )
    finally:
        if engine is not None:
            engine.dispose()

    return ReadinessCheck(name="database_url", status="ok")


def _media_root_check(settings: Settings) -> ReadinessCheck:
    if not settings.media_root.exists():
        return ReadinessCheck(
            name="media_root",
            status="failed",
            detail=f"Media root does not exist: {settings.media_root}",
        )
    if not settings.media_root.is_dir():
        return ReadinessCheck(
            name="media_root",
            status="failed",
            detail=f"Media root is not a directory: {settings.media_root}",
        )
    return ReadinessCheck(name="media_root", status="ok")


def _executable_check(name: str, executable: str) -> ReadinessCheck:
    if which(executable) is None:
        return ReadinessCheck(
            name=name,
            status="failed",
            detail=f"Executable is not available: {executable}",
        )
    return ReadinessCheck(name=name, status="ok")
