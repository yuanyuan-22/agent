from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from forge.config import settings
from forge.content_plan import GenerationRequest, GenerationResult
from .base import GenerationProvider


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {settings.siliconflow_api_key}"}


def _base() -> str:
    return settings.siliconflow_base_url.rstrip("/")


def _image_size(aspect_ratio: str) -> str:
    if settings.image_size:
        return settings.image_size
    return {
        "9:16": "768x1344",
        "16:9": "1344x768",
        "1:1": "1024x1024",
    }.get(aspect_ratio or "9:16", "768x1344")


def _download(url: str, target: Path, timeout: float) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
        resp.raise_for_status()
        with target.open("wb") as handle:
            for chunk in resp.iter_bytes():
                handle.write(chunk)


class SiliconFlowImageProvider(GenerationProvider):
    name = "siliconflow_image"

    def __init__(self, model: str | None = None):
        self.model = model or settings.image_model

    def generate_image(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        if not settings.siliconflow_api_key:
            return GenerationResult(ok=False, kind="image", provider=self.name,
                                    model=self.model, prompt=request.prompt,
                                    error="missing SILICONFLOW_API_KEY")
        started = time.time()
        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "image_size": _image_size(request.aspect_ratio),
            "batch_size": 1,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
        }
        if request.seed is not None:
            payload["seed"] = request.seed
        target = work_dir / "generated" / "images" / f"{_task_id(request)}.png"
        if target.exists():
            return GenerationResult(
                ok=True, kind="image", provider=self.name, model=self.model,
                path=str(target), prompt=request.prompt, seed=request.seed,
                metadata={"cache_hit": True},
            )
        try:
            resp = httpx.post(
                f"{_base()}{settings.image_endpoint}",
                json=payload,
                headers=_headers(),
                timeout=settings.generation_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            item = _first_image_item(data)
            if item.get("url"):
                _download(item["url"], target, settings.generation_timeout)
            elif item.get("b64_json"):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(base64.b64decode(item["b64_json"]))
            else:
                raise RuntimeError("image response missing url/b64_json")
            return GenerationResult(
                ok=True, kind="image", provider=self.name, model=self.model,
                path=str(target), prompt=request.prompt, seed=request.seed,
                latency_ms=int((time.time() - started) * 1000),
                metadata={"api_response": data},
            )
        except Exception as exc:  # noqa: BLE001
            return GenerationResult(
                ok=False, kind="image", provider=self.name, model=self.model,
                prompt=request.prompt, seed=request.seed,
                latency_ms=int((time.time() - started) * 1000), error=str(exc),
            )

    def generate_video(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        return GenerationResult(
            ok=False, kind="video", provider=self.name, model=self.model,
            prompt=request.prompt, error="image provider cannot generate video",
        )


class SiliconFlowVideoProvider(GenerationProvider):
    name = "siliconflow_video"

    def __init__(self, model: str | None = None):
        self.model = model or settings.video_model

    def generate_image(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        return GenerationResult(
            ok=False, kind="image", provider=self.name, model=self.model,
            prompt=request.prompt, error="video provider cannot generate image",
        )

    def generate_video(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        if not settings.siliconflow_api_key:
            return GenerationResult(ok=False, kind="video", provider=self.name,
                                    model=self.model, prompt=request.prompt,
                                    error="missing SILICONFLOW_API_KEY")
        started = time.time()
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": request.prompt,
            "duration": max(2, min(int(request.duration_sec or 5), 10)),
        }
        if request.image_path:
            payload["image"] = _image_data_uri(Path(request.image_path))
        target = work_dir / "generated" / "videos" / f"{_task_id(request)}.mp4"
        if target.exists():
            return GenerationResult(
                ok=True, kind="video", provider=self.name, model=self.model,
                path=str(target), prompt=request.prompt, seed=request.seed,
                metadata={"cache_hit": True},
            )
        try:
            submit = httpx.post(
                f"{_base()}{settings.video_submit_endpoint}",
                json=payload,
                headers=_headers(),
                timeout=settings.generation_timeout,
            )
            submit.raise_for_status()
            data = submit.json()
            request_id = data.get("requestId") or data.get("request_id") or data.get("id") or data.get("task_id")
            if not request_id:
                raise RuntimeError(f"video submit missing request id: {data}")
            video_url = _poll_video(request_id)
            _download(video_url, target, settings.generation_timeout)
            return GenerationResult(
                ok=True, kind="video", provider=self.name, model=self.model,
                path=str(target), prompt=request.prompt, seed=request.seed,
                latency_ms=int((time.time() - started) * 1000),
                metadata={"request_id": request_id, "api_response": data},
            )
        except Exception as exc:  # noqa: BLE001
            return GenerationResult(
                ok=False, kind="video", provider=self.name, model=self.model,
                prompt=request.prompt, seed=request.seed,
                latency_ms=int((time.time() - started) * 1000), error=str(exc),
            )


def _first_image_item(data: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("images", "data"):
        items = data.get(key)
        if isinstance(items, list) and items:
            item = items[0]
            return item if isinstance(item, dict) else {"url": item}
    if data.get("url"):
        return data
    raise RuntimeError(f"unexpected image response: {data}")


def _poll_video(request_id: str) -> str:
    deadline = time.time() + settings.video_poll_interval * settings.video_poll_max
    while time.time() < deadline:
        resp = httpx.get(
            f"{_base()}{settings.video_status_endpoint}",
            params={"requestId": request_id},
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = str(data.get("status") or data.get("state") or "").lower()
        url = _video_url(data)
        if url and status in ("succeed", "succeeded", "success", "completed", "done", ""):
            return url
        if status in ("failed", "error", "cancelled"):
            raise RuntimeError(f"video generation failed: {data}")
        time.sleep(settings.video_poll_interval)
    raise TimeoutError("video generation polling timeout")


def _video_url(data: Dict[str, Any]) -> str:
    for key in ("video_url", "url", "output_url"):
        if data.get(key):
            return str(data[key])
    for key in ("videos", "results", "data"):
        items = data.get(key)
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                for url_key in ("url", "video_url", "output_url"):
                    if first.get(url_key):
                        return str(first[url_key])
    return ""


def _task_id(request: GenerationRequest) -> str:
    raw = f"{request.kind}:{request.prompt}:{request.seed}:{request.image_path}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _image_data_uri(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix
    return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
