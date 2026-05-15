from __future__ import annotations

import logging

from shorts_factory.settings import Settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        format=LOG_FORMAT,
        force=False,
    )
