from collections.abc import Generator
from secrets import compare_digest
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from shorts_factory.db.models import PublishPlatform
from shorts_factory.db.repositories import JobNotFoundError, VideoJobRepository
from shorts_factory.db.session import create_session_factory, get_engine, session_scope
from shorts_factory.jobs.scheduler import create_manual_job
from shorts_factory.publishing.publish_service import DuplicatePublishError, PublishService
from shorts_factory.publishing.telegram_publisher import TelegramPublisher, TelegramPublishError
from shorts_factory.settings import Settings


class CreateJobRequest(BaseModel):
    quiz_id: str | None = None
    target_platforms: list[PublishPlatform] = Field(
        default_factory=lambda: [PublishPlatform.TELEGRAM]
    )


class JobResponse(BaseModel):
    id: int
    quiz_id: str | None
    status: str
    locale: str
    level: str | None
    topic: str | None
    target_platforms: list[str]
    retry_count: int
    video_path: str | None
    duration_sec: float | None
    error_message: str | None
    script_json: dict[str, Any] | None
    render_plan_json: dict[str, Any] | None


class AssetResponse(BaseModel):
    id: int
    type: str
    path: str
    checksum: str
    metadata_json: dict[str, Any] | None


def create_jobs_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/jobs", tags=["jobs"])
    engine = get_engine(settings)
    session_factory = create_session_factory(engine) if engine is not None else None

    def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if settings.api_key is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SHORTS_FACTORY_API_KEY is not configured.",
            )
        expected = settings.api_key.get_secret_value()
        if x_api_key is None or not compare_digest(x_api_key, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

    def get_session() -> Generator[Session]:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is not configured.",
            )
        yield from session_scope(session_factory)

    Auth = Depends(verify_api_key)

    @router.post("/create", response_model=JobResponse, dependencies=[Auth])
    def create_job(
        payload: CreateJobRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> JobResponse:
        repository = VideoJobRepository(session)
        job_id = create_manual_job(
            repository,
            quiz_id=payload.quiz_id,
            target_platforms=[platform.value for platform in payload.target_platforms],
        )
        job = repository.get(job_id)
        return _job_response(job)

    @router.get("", response_model=list[JobResponse], dependencies=[Auth])
    def list_jobs(
        session: Annotated[Session, Depends(get_session)],
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobResponse]:
        repository = VideoJobRepository(session)
        return [_job_response(job) for job in repository.list(limit=limit, offset=offset)]

    @router.get("/{job_id}", response_model=JobResponse, dependencies=[Auth])
    def get_job(job_id: int, session: Annotated[Session, Depends(get_session)]) -> JobResponse:
        repository = VideoJobRepository(session)
        try:
            job = repository.get_with_children(job_id)
        except JobNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        return _job_response(job)

    @router.get("/{job_id}/assets", response_model=list[AssetResponse], dependencies=[Auth])
    def get_assets(
        job_id: int, session: Annotated[Session, Depends(get_session)]
    ) -> list[AssetResponse]:
        repository = VideoJobRepository(session)
        try:
            job = repository.get_with_children(job_id)
        except JobNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        return [
            AssetResponse(
                id=asset.id,
                type=asset.type,
                path=asset.path,
                checksum=asset.checksum,
                metadata_json=asset.metadata_json,
            )
            for asset in job.assets
        ]

    @router.post("/{job_id}/retry", response_model=JobResponse, dependencies=[Auth])
    def retry_job(job_id: int, session: Annotated[Session, Depends(get_session)]) -> JobResponse:
        repository = VideoJobRepository(session)
        try:
            job = repository.increment_retry(repository.get(job_id))
        except JobNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        return _job_response(job)

    @router.post("/{job_id}/publish/telegram", response_model=JobResponse, dependencies=[Auth])
    def publish_telegram(
        job_id: int, session: Annotated[Session, Depends(get_session)]
    ) -> JobResponse:
        repository = VideoJobRepository(session)
        try:
            job = repository.get(job_id)
            publisher = TelegramPublisher(settings)
            PublishService(repository, publisher).publish_to_telegram(job)
        except JobNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except (TelegramPublishError, DuplicatePublishError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        return _job_response(job)

    @router.post("/{job_id}/publish/youtube", dependencies=[Auth])
    def publish_youtube(job_id: int) -> dict[str, str]:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"YouTube publishing belongs to Stage 2. Job {job_id} was not published.",
        )

    return router


def _job_response(job: Any) -> JobResponse:
    return JobResponse(
        id=job.id,
        quiz_id=job.quiz_id,
        status=job.status,
        locale=job.locale,
        level=job.level,
        topic=job.topic,
        target_platforms=job.target_platforms,
        retry_count=job.retry_count,
        video_path=job.video_path,
        duration_sec=job.duration_sec,
        error_message=job.error_message,
        script_json=job.script_json,
        render_plan_json=job.render_plan_json,
    )
