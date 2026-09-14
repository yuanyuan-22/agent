from __future__ import annotations

from pathlib import Path

from PIL import Image

from forge.config import settings
from forge.content_plan import CharacterBible, GenerationRequest
from .manager import GenerationManager


class CharacterManager:
    def __init__(self, generation: GenerationManager | None = None):
        self.generation = generation or GenerationManager()

    def ensure(self, bible: CharacterBible, work_dir: Path) -> CharacterBible:
        target = settings.character_dir / f"{bible.character_id}.png"
        if target.exists():
            bible.base_image_path = str(target)
            return bible

        prompt = (
            f"{bible.description}. {bible.style_prompt}. "
            "Full body flat vector character, centered, friendly teacher presenter, "
            "solid pure green background (#00ff00), no shadows, no text, no logo."
        )
        result = self.generation.generate_image(
            GenerationRequest(
                kind="image",
                prompt=prompt,
                aspect_ratio="9:16",
                seed=bible.seed,
                metadata={"role": "presenter"},
            ),
            work_dir,
        )
        if result.ok and result.path:
            _chroma_key_green(Path(result.path), target)
            bible.base_image_path = str(target)
        return bible


def _chroma_key_green(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if g > 150 and g > r * 1.35 and g > b * 1.35:
                pixels[x, y] = (r, g, b, 0)
    image.save(target)
