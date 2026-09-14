from pathlib import Path

from forge.assets import AssetManager, LocalAssetProvider, PexelsProvider


def test_local_asset_provider_selects_keyword_match(tmp_path):
    (tmp_path / "autumn-city.jpg").write_bytes(b"jpg")
    (tmp_path / "ocean.jpg").write_bytes(b"jpg")
    provider = LocalAssetProvider(tmp_path)
    asset = provider.search("autumn city", "image", tmp_path)
    assert asset is not None
    assert Path(asset.path).name == "autumn-city.jpg"
    assert asset.kind == "image"


def test_asset_manager_skips_used_fingerprint(tmp_path):
    (tmp_path / "one.jpg").write_bytes(b"one")
    # 不同内容避免 fingerprint 相同；第二次应回退到 card/None。
    provider = LocalAssetProvider(tmp_path)
    manager = AssetManager([provider])
    first = manager.resolve({"visual_query": "one", "visual_type": "image"}, tmp_path)
    second = manager.resolve({"visual_query": "one", "visual_type": "image"}, tmp_path,
                             used={first.fingerprint})
    assert first is not None
    assert second is None


def test_pexels_provider_parses_photo(monkeypatch, tmp_path):
    provider = PexelsProvider("test-key")
    monkeypatch.setattr(provider, "_request", lambda endpoint, query: {
        "photos": [{
            "src": {"large2x": "https://images.example/photo.jpg"},
            "url": "https://www.pexels.com/photo/1",
            "photographer": "Photographer",
        }]
    })

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"image"

    monkeypatch.setattr("forge.assets.httpx.stream", lambda *args, **kwargs: FakeResponse())
    asset = provider.search("autumn", "image", tmp_path)
    assert asset is not None
    assert asset.provider == "pexels"
    assert asset.author == "Photographer"
    assert Path(asset.path).exists()
