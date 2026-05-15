from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class JobStatus(StrEnum):
    CREATED = "created"
    QUIZ_LOADED = "quiz_loaded"
    QUIZ_VALIDATED = "quiz_validated"
    SCRIPT_READY = "script_ready"
    IMAGES_READY = "images_ready"
    AUDIO_READY = "audio_ready"
    RENDER_PLAN_READY = "render_plan_ready"
    RENDERED = "rendered"
    QA_PASSED = "qa_passed"
    TELEGRAM_PUBLISHED = "telegram_published"
    YOUTUBE_PUBLISHED = "youtube_published"
    DONE = "done"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class AssetType(StrEnum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    SUBTITLE = "subtitle"


class PublishPlatform(StrEnum):
    TELEGRAM = "telegram"
    YOUTUBE = "youtube"


class RecordStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quiz_id: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), default=JobStatus.CREATED.value, index=True)
    locale: Mapped[str] = mapped_column(String(16), default="de-DE")
    level: Mapped[str | None] = mapped_column(String(64))
    topic: Mapped[str | None] = mapped_column(String(128))
    target_platforms: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["telegram"])
    script_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    render_plan_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    video_path: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assets: Mapped[list[VideoAsset]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    publish_logs: Mapped[list[PublishLog]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    render_logs: Mapped[list[RenderLog]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("video_jobs.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[VideoJob] = relationship(back_populates="assets")


class PublishLog(Base):
    __tablename__ = "publish_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("video_jobs.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default=RecordStatus.PENDING.value)
    external_id: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[VideoJob] = relationship(back_populates="publish_logs")


class RenderLog(Base):
    __tablename__ = "render_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("video_jobs.id"), index=True)
    step: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[VideoJob] = relationship(back_populates="render_logs")


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    duration_sec: Mapped[float] = mapped_column(Float)
    frame_count: Mapped[int] = mapped_column(Integer)
    style_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
