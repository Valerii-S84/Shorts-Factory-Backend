from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from shorts_factory.db.models import (
    AssetType,
    JobStatus,
    PublishLog,
    PublishPlatform,
    RecordStatus,
    RenderLog,
    VideoAsset,
    VideoJob,
)


class JobNotFoundError(ValueError):
    pass


class VideoJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        quiz_id: str | None = None,
        locale: str = "de-DE",
        target_platforms: Sequence[str] | None = None,
    ) -> VideoJob:
        platforms = (
            list(target_platforms)
            if target_platforms is not None
            else [PublishPlatform.TELEGRAM.value]
        )
        job = VideoJob(
            quiz_id=quiz_id,
            locale=locale,
            target_platforms=platforms,
        )
        self._session.add(job)
        self._session.flush()
        return job

    def get(self, job_id: int) -> VideoJob:
        job = self._session.get(VideoJob, job_id)
        if job is None:
            raise JobNotFoundError(f"Video job does not exist: {job_id}")
        return job

    def get_with_children(self, job_id: int) -> VideoJob:
        statement = self._base_statement().where(VideoJob.id == job_id)
        job = self._session.scalars(statement).first()
        if job is None:
            raise JobNotFoundError(f"Video job does not exist: {job_id}")
        return job

    def list(self, *, limit: int = 50, offset: int = 0) -> list[VideoJob]:
        statement = self._base_statement().order_by(VideoJob.id.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(statement).all())

    def update_status(
        self,
        job: VideoJob,
        status: JobStatus,
        *,
        error_message: str | None = None,
        finished: bool = False,
    ) -> VideoJob:
        job.status = status.value
        job.error_message = error_message
        job.updated_at = datetime.now(UTC)
        if finished:
            job.finished_at = datetime.now(UTC)
        self._session.flush()
        return job

    def store_script(self, job: VideoJob, script_json: dict[str, Any]) -> VideoJob:
        job.script_json = script_json
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        return job

    def store_render_plan(self, job: VideoJob, render_plan_json: dict[str, Any]) -> VideoJob:
        job.render_plan_json = render_plan_json
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        return job

    def store_video_result(
        self, job: VideoJob, *, video_path: str, duration_sec: float
    ) -> VideoJob:
        job.video_path = video_path
        job.duration_sec = duration_sec
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        return job

    def increment_retry(self, job: VideoJob) -> VideoJob:
        job.retry_count += 1
        job.status = JobStatus.RETRY_PENDING.value
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        return job

    def add_asset(
        self,
        job: VideoJob,
        *,
        asset_type: AssetType,
        path: str,
        checksum: str,
        metadata: dict[str, Any] | None = None,
    ) -> VideoAsset:
        asset = VideoAsset(
            job_id=job.id,
            type=asset_type.value,
            path=path,
            checksum=checksum,
            metadata_json=metadata,
        )
        self._session.add(asset)
        self._session.flush()
        return asset

    def add_render_log(
        self,
        job: VideoJob,
        *,
        step: str,
        status: RecordStatus,
        message: str | None = None,
    ) -> RenderLog:
        render_log = RenderLog(
            job_id=job.id,
            step=step,
            status=status.value,
            message=message,
        )
        self._session.add(render_log)
        self._session.flush()
        return render_log

    def add_publish_log(
        self,
        job: VideoJob,
        *,
        platform: PublishPlatform,
        status: RecordStatus,
        external_id: str | None = None,
        url: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PublishLog:
        publish_log = PublishLog(
            job_id=job.id,
            platform=platform.value,
            status=status.value,
            external_id=external_id,
            url=url,
            error_message=error_message,
            metadata_json=metadata,
            published_at=datetime.now(UTC) if status == RecordStatus.SUCCESS else None,
        )
        self._session.add(publish_log)
        self._session.flush()
        return publish_log

    def has_successful_publish(self, job: VideoJob, platform: PublishPlatform) -> bool:
        statement = select(PublishLog).where(
            PublishLog.job_id == job.id,
            PublishLog.platform == platform.value,
            PublishLog.status == RecordStatus.SUCCESS.value,
        )
        return self._session.scalars(statement).first() is not None

    def _base_statement(self) -> Select[tuple[VideoJob]]:
        return select(VideoJob).options(
            selectinload(VideoJob.assets),
            selectinload(VideoJob.publish_logs),
            selectinload(VideoJob.render_logs),
        )
