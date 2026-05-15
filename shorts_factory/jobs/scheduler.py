from __future__ import annotations

from shorts_factory.db.repositories import VideoJobRepository


def create_manual_job(
    repository: VideoJobRepository,
    *,
    quiz_id: str | None = None,
    target_platforms: list[str] | None = None,
) -> int:
    job = repository.create(quiz_id=quiz_id, target_platforms=target_platforms)
    return job.id
