from __future__ import annotations

import base64
from pathlib import Path
from typing import Protocol

from openai import OpenAI

from shorts_factory.generation.schemas import GeneratedScript
from shorts_factory.settings import Settings
from shorts_factory.storage.asset_paths import job_asset_path
from shorts_factory.storage.local_storage import LocalStorage


class ImageGenerationError(RuntimeError):
    pass


class ImageGenerator(Protocol):
    def generate(self, *, job_id: int, script: GeneratedScript) -> list[Path]:
        pass


class OpenAIImageGenerator:
    def __init__(
        self,
        settings: Settings,
        storage: LocalStorage,
        client: OpenAI | None = None,
    ) -> None:
        if settings.openai_api_key is None:
            raise ImageGenerationError("OPENAI_API_KEY is not configured.")
        self._settings = settings
        self._storage = storage
        self._client = client or OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def generate(self, *, job_id: int, script: GeneratedScript) -> list[Path]:
        image_paths = []
        for index, frame in enumerate(script.frames, start=1):
            response = self._client.images.generate(
                model=self._settings.openai_image_model,
                prompt=frame.image_prompt,
                size="1024x1792",
            )
            image_data = response.data[0]
            if image_data.b64_json is None:
                raise ImageGenerationError("OpenAI image response did not include b64_json.")

            path = job_asset_path(self._settings, job_id, "images", f"frame_{index:02d}.png")
            self._storage.write_bytes(path, base64.b64decode(image_data.b64_json))
            image_paths.append(path)
        return image_paths
