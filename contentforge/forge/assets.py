from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx

from forge.config import settings
from forge.content_plan import GenerationRequest, GenerationResult
from forge.generation.manager import GenerationManager

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}


@dataclass
class AssetRef:
    kind: str
    path: str
    provider: str
    query: str = ""
    author: str = ""
    source_url: str = ""
    fingerprint: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseAssetProvider:
    name = "base"

    def search(self, query: str, kind: str, work_dir: Path) -> Optional[AssetRef]:
        raise NotImplementedError


class LocalAssetProvider(BaseAssetProvider):
    name = "local"

    def __init__(self, root: Path | None = None):
        self.root = Path(root or settings.asset_dir)

    def _candidates(self) -> List[Path]:
        if not self.root.exists():
            return []
        allowed = IMAGE_EXT | VIDEO_EXT
        return [
            path for path in self.root.rglob("*")
            if path.is_file() and path.suffix.lower() in allowed
        ]

    def search(self, query: str, kind: str, work_dir: Path) -> Optional[AssetRef]:
        tokens = [t.lower() for t in (query or "").replace("，", " ").replace(",", " ").split() if t]
        candidates = self._candidates()
        if kind == "image":
            candidates = [p for p in candidates if p.suffix.lower() in IMAGE_EXT]
        elif kind == "video":
            candidates = [p for p in candidates if p.suffix.lower() in VIDEO_EXT]
        if not candidates:
            return None

        def score(path: Path) -> int:
            name = path.stem.lower()
            return sum(1 for token in tokens if token and token in name)

        candidates.sort(key=score, reverse=True)
        pick = candidates[0]
        return AssetRef(
            kind="video" if pick.suffix.lower() in VIDEO_EXT else "image",
            path=str(pick),
            provider=self.name,
            query=query,
            author="local",
            source_url="",
            fingerprint=_fingerprint(pick),
        )


class PexelsProvider(BaseAssetProvider):
    name = "pexels"

    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key if api_key is not None else settings.pexels_api_key).strip()

    def _request(self, endpoint: str, query: str) -> Dict[str, Any]:
        if not self.api_key:
            return {}
        resp = httpx.get(
            endpoint,
            params={"query": query, "per_page": 5, "orientation": "portrait"},
            headers={"Authorization": self.api_key},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def search(self, query: str, kind: str, work_dir: Path) -> Optional[AssetRef]:
        if not settings.pexels_enabled or not self.api_key or not query:
            return None
        if kind == "video":
            data = self._request("https://api.pexels.com/videos/search", query)
            candidates = data.get("videos") or []
        else:
            data = self._request("https://api.pexels.com/v1/search", query)
            candidates = data.get("photos") or []
        if not candidates:
            return None
        item = candidates[0]
        if kind == "video":
            files = item.get("video_files") or []
            if not files:
                return None
            url = next((f.get("link") for f in sorted(files, key=lambda x: x.get("width", 0) >= 720, reverse=True)
                        if f.get("link")), "")
            source_url = item.get("url") or ""
            author = item.get("user", {}).get("name", "")
        else:
            url = ((item.get("src") or {}).get("large2x")
                   or (item.get("src") or {}).get("large")
                   or (item.get("src") or {}).get("original"))
            source_url = item.get("url") or ""
            author = item.get("photographer") or ""
        if not url:
            return None
        save_dir = work_dir / "assets"
        save_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(httpx.URL(url).path).suffix or (".mp4" if kind == "video" else ".jpg")
        target = save_dir / f"{_safe_name(query)}-{hashlib.sha1(url.encode()).hexdigest()[:10]}{suffix}"
        if not target.exists():
            with httpx.stream("GET", url, timeout=60, follow_redirects=True) as resp:
                resp.raise_for_status()
                with target.open("wb") as handle:
                    for chunk in resp.iter_bytes():
                        handle.write(chunk)
        return AssetRef(
            kind=kind,
            path=str(target),
            provider=self.name,
            query=query,
            author=author,
            source_url=source_url,
            fingerprint=_fingerprint(target),
            meta={"download_url": url},
        )


class AssetManager:
    def __init__(self, providers: Iterable[BaseAssetProvider] | None = None,
                 generation_manager: GenerationManager | None = None):
        self.providers = list(providers or [PexelsProvider(), LocalAssetProvider()])
        self.generation_manager = generation_manager or GenerationManager()

    def resolve(self, segment: Dict[str, Any], work_dir: Path,
                used: set[str] | None = None) -> Optional[AssetRef]:
        kind = (segment.get("visual_type") or "image").strip().lower()
        if kind == "card":
            return None
        if kind not in ("image", "video"):
            kind = "image"
        query = (segment.get("visual_query") or segment.get("heading") or "").strip()
        if not query:
            query = (segment.get("caption") or segment.get("text") or "")[:30]
        used = used if used is not None else set()

        policy = (segment.get("asset_policy") or "").strip().lower()
        if policy.startswith("generate") and settings.generation_first:
            generated = self._generate_scene(segment, work_dir, used, query)
            if generated is not None:
                return generated

        for provider in self.providers:
            try:
                asset = provider.search(query, kind, work_dir)
            except Exception:
                asset = None
            if asset and asset.fingerprint not in used:
                used.add(asset.fingerprint)
                return asset
        if policy.startswith("generate"):
            generated = self._generate_scene(segment, work_dir, used, query)
            if generated is not None:
                return generated
        return None

    def _generate_scene(self, segment: Dict[str, Any], work_dir: Path,
                        used: set[str], query: str) -> Optional[AssetRef]:
        style = (segment.get("style_prompt") or "").strip()
        character = segment.get("character") or {}
        character_prompt = ""
        if segment.get("show_character") and character:
            character_prompt = (
                f" Include a consistent flat vector presenter character: "
                f"{character.get('description', '')}."
            )
        base_prompt = (
            f"{style}. {query}. Aspect ratio 9:16. "
            "No large text, no watermark, no logo." + character_prompt
        )
        policy = (segment.get("asset_policy") or "").strip().lower()
        image_result: GenerationResult | None = None
        if policy == "generate_video":
            image_result = self.generation_manager.generate_image(
                GenerationRequest(
                    kind="image",
                    prompt=base_prompt,
                    aspect_ratio="9:16",
                    seed=_scene_seed(segment),
                ),
                work_dir,
            )
            if image_result.ok:
                video_prompt = (segment.get("video_prompt") or base_prompt).strip()
                video_result = self.generation_manager.generate_video(
                    GenerationRequest(
                        kind="video",
                        prompt=f"{style}. {video_prompt}",
                        image_path=image_result.path,
                        duration_sec=float(segment.get("duration_hint") or 5),
                        seed=_scene_seed(segment),
                    ),
                    work_dir,
                )
                ref = _result_to_asset(video_result, query)
                if ref and ref.fingerprint not in used:
                    used.add(ref.fingerprint)
                    return ref
                image_result.fallback_from = video_result.model or video_result.provider
                image_result.error = video_result.error or "video generation failed, using keyframe image"

        if image_result is None:
            image_result = self.generation_manager.generate_image(
                GenerationRequest(
                    kind="image",
                    prompt=base_prompt,
                    aspect_ratio="9:16",
                    seed=_scene_seed(segment),
                ),
                work_dir,
            )
        ref = _result_to_asset(image_result, query)
        if ref and ref.fingerprint not in used:
            used.add(ref.fingerprint)
            return ref
        return None


def _fingerprint(path: Path) -> str:
    try:
        stat = path.stat()
        return hashlib.sha1(f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")).hexdigest()
    except OSError:
        return hashlib.sha1(str(path).encode("utf-8")).hexdigest()


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)[:40] or "asset"


def _scene_seed(segment: Dict[str, Any]) -> int:
    raw = f"{segment.get('shot_id')}:{segment.get('visual_prompt')}:{segment.get('video_prompt')}"
    return int(hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8], 16)


def _result_to_asset(result: GenerationResult, query: str) -> Optional[AssetRef]:
    if not result.ok or not result.path or not Path(result.path).exists():
        return None
    return AssetRef(
        kind=result.kind,
        path=result.path,
        provider=result.provider,
        query=query,
        author=result.model,
        source_url="",
        fingerprint=_fingerprint(Path(result.path)),
        meta=result.to_dict(),
    )
