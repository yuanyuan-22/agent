from pathlib import Path

from PIL import Image

from forge.content_plan import CharacterBible, GenerationRequest, GenerationResult
from forge.generation.base import GenerationProvider
from forge.generation.character import CharacterManager, _chroma_key_green
from forge.generation.manager import GenerationManager
from forge.config import settings as app_settings


class _FakeProvider(GenerationProvider):
    def __init__(self, name, fail=False, kind="image"):
        self.name = name
        self.fail = fail
        self.kind = kind

    def _result(self, request, work_dir):
        if self.fail:
            return GenerationResult(ok=False, kind=self.kind, provider=self.name,
                                    model=self.name, prompt=request.prompt, error="failed")
        target = work_dir / f"{self.name}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (20, 30), (10, 20, 30)).save(target)
        return GenerationResult(ok=True, kind=self.kind, provider=self.name,
                                model=self.name, path=str(target), prompt=request.prompt)

    def generate_image(self, request, work_dir):
        return self._result(request, work_dir)

    def generate_video(self, request, work_dir):
        return GenerationResult(ok=False, kind="video", provider=self.name,
                                model=self.name, prompt=request.prompt, error="not video")


def test_generation_manager_falls_back_to_second_provider(tmp_path):
    manager = GenerationManager([
        _FakeProvider("fail", fail=True),
        _FakeProvider("ok"),
    ])
    result = manager.generate_image(
        GenerationRequest(kind="image", prompt="test"), tmp_path
    )
    assert result.ok is True
    assert result.provider == "ok"


def test_ai_video_generation_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(app_settings, "video_generation_enabled", False)
    manager = GenerationManager(providers=[])
    result = manager.generate_video(
        GenerationRequest(kind="video", prompt="test"), tmp_path
    )
    assert result.ok is False
    assert "disabled" in result.error
    assert result.metadata["attempts"]


def test_chroma_key_and_character_cache(tmp_path, monkeypatch):
    source = tmp_path / "green.png"
    image = Image.new("RGB", (10, 10), (0, 255, 0))
    image.putpixel((5, 5), (30, 30, 30))
    image.save(source)
    target = tmp_path / "cutout.png"
    _chroma_key_green(source, target)
    assert Image.open(target).convert("RGBA").getpixel((0, 0))[3] == 0
    assert Image.open(target).convert("RGBA").getpixel((5, 5))[3] == 255

    class _Manager:
        def generate_image(self, request, work_dir):
            return GenerationResult(
                ok=True, kind="image", provider="fake", model="fake",
                path=str(source), prompt=request.prompt,
            )

    monkeypatch.setattr("forge.generation.character.settings.character_dir", tmp_path / "characters")
    bible = CharacterManager(_Manager()).ensure(CharacterBible(), tmp_path)
    assert Path(bible.base_image_path).exists()
