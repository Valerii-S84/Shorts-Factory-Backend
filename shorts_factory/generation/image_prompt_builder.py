from __future__ import annotations

from shorts_factory.generation.image_style_contract import PRODUCTION_IMAGE_STYLE_CONTRACT

IMAGE_NEGATIVE_RULES = (
    "no visible text",
    "no letters",
    "no captions",
    "no UI",
    "no logos",
    "no watermarks",
    "no question text",
    "no answer options",
)

IMAGE_COMPOSITION_RULES = (
    "main subject centered in upper/middle area",
    "lower third visually calm for backend overlay",
)


class ImagePromptBuilder:
    def build(self, scene_brief: str) -> str:
        stripped_scene_brief = scene_brief.strip()
        if not stripped_scene_brief:
            raise ValueError("Image scene brief must not be empty.")

        negative_rules = "\n".join(f"- {rule}" for rule in IMAGE_NEGATIVE_RULES)
        composition_rules = "\n".join(f"- {rule}" for rule in IMAGE_COMPOSITION_RULES)
        return (
            "Style contract:\n"
            f"{PRODUCTION_IMAGE_STYLE_CONTRACT}\n\n"
            "Scene brief:\n"
            f"{stripped_scene_brief}\n\n"
            "Negative rules:\n"
            f"{negative_rules}\n\n"
            "Composition:\n"
            f"{composition_rules}"
        )
