from __future__ import annotations

from shorts_factory.settings import Settings


def prepare_runtime_paths(settings: Settings) -> None:
    settings.media_root.mkdir(parents=True, exist_ok=True)
