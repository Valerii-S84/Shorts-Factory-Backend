from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

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
    ]
    return checks


def _database_url_check(settings: Settings) -> ReadinessCheck:
    if settings.database_url is None:
        return ReadinessCheck(
            name="database_url",
            status="failed",
            detail="DATABASE_URL is not configured.",
        )
    return ReadinessCheck(name="database_url", status="ok")


def _media_root_check(settings: Settings) -> ReadinessCheck:
    parent = settings.media_root.parent
    if not parent.exists():
        return ReadinessCheck(
            name="media_root_parent",
            status="failed",
            detail=f"Media root parent does not exist: {parent}",
        )
    return ReadinessCheck(name="media_root_parent", status="ok")
