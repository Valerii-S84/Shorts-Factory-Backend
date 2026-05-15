from __future__ import annotations

from pathlib import Path

from shorts_factory.settings import Settings


def job_asset_dir(settings: Settings, job_id: int, asset_group: str) -> Path:
    root_by_group = {
        "images": settings.images_root,
        "audio": settings.audio_root,
        "videos": settings.videos_root,
    }
    root = root_by_group.get(asset_group, settings.media_root / asset_group)
    return root / str(job_id)


def job_asset_path(settings: Settings, job_id: int, asset_group: str, filename: str) -> Path:
    return job_asset_dir(settings, job_id, asset_group) / filename
