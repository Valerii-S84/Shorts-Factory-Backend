from __future__ import annotations

from shorts_factory.generation.schemas import GeneratedScript


def telegram_caption(script: GeneratedScript) -> str:
    return script.telegram_caption.strip()


def youtube_title(script: GeneratedScript) -> str:
    return script.youtube_title.strip()


def youtube_description(script: GeneratedScript) -> str:
    return script.youtube_description.strip()
