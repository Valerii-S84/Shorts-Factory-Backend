from __future__ import annotations

from fastapi import FastAPI

from shorts_factory import __version__
from shorts_factory.api.health import create_health_router
from shorts_factory.logging_config import configure_logging
from shorts_factory.runtime import prepare_runtime_paths
from shorts_factory.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    prepare_runtime_paths(resolved_settings)

    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
    )
    app.state.settings = resolved_settings
    app.include_router(create_health_router(resolved_settings))
    return app


app = create_app()
