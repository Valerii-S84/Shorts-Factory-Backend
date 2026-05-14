from __future__ import annotations

from shorts_factory.db.models import Base
from shorts_factory.db.session import create_database_engine
from shorts_factory.settings import Settings


def prepare_runtime_paths(settings: Settings) -> None:
    settings.media_root.mkdir(parents=True, exist_ok=True)
    settings.images_root.mkdir(parents=True, exist_ok=True)
    settings.audio_root.mkdir(parents=True, exist_ok=True)
    settings.videos_root.mkdir(parents=True, exist_ok=True)


def prepare_local_database(settings: Settings) -> None:
    if settings.environment not in {"local", "test", "development"}:
        return
    database_url = settings.effective_database_url
    if database_url is None:
        return
    engine = create_database_engine(database_url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
