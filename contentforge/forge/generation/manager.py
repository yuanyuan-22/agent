from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from forge.config import settings
from forge.content_plan import GenerationRequest, GenerationResult
from .base import GenerationProvider
from .siliconflow import SiliconFlowImageProvider, SiliconFlowVideoProvider


class GenerationManager:
    def __init__(self, providers: Iterable[GenerationProvider] | None = None):
        self.providers = list(providers or [
            SiliconFlowImageProvider(),
            SiliconFlowImageProvider(settings.image_fallback_model),
            SiliconFlowVideoProvider(),
        ])

    def generate_image(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        return self._try(request, work_dir, "image")

    def generate_video(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        if not settings.video_generation_enabled:
            result = GenerationResult(
                ok=False,
                kind="video",
                prompt=request.prompt,
                error="AI video generation disabled",
            )
            result.metadata = {"attempts": [result.to_dict()]}
            return result
        return self._try(request, work_dir, "video")

    def _try(self, request: GenerationRequest, work_dir: Path, kind: str) -> GenerationResult:
        if not settings.generation_enabled:
            return GenerationResult(
                ok=False, kind=kind, prompt=request.prompt,
                error="generation disabled",
            )
        attempts: List[GenerationResult] = []
        for provider in self.providers:
            for _ in range(max(1, settings.generation_retries + 1)):
                result = (
                    provider.generate_image(request, work_dir)
                    if kind == "image"
                    else provider.generate_video(request, work_dir)
                )
                attempts.append(result)
                if result.ok:
                    if attempts[:-1]:
                        result.fallback_from = attempts[-2].model or attempts[-2].provider
                    result.metadata = {
                        **(result.metadata or {}),
                        "attempts": [item.to_dict() for item in attempts],
                    }
                    return result
        last = attempts[-1] if attempts else GenerationResult(ok=False, kind=kind, error="no provider")
        last.metadata = {**(last.metadata or {}), "attempts": [item.to_dict() for item in attempts]}
        return last

    def capabilities(self) -> dict:
        return {
            "generation_enabled": settings.generation_enabled,
            "generation_first": settings.generation_first,
            "video_generation_enabled": settings.video_generation_enabled,
            "image_model": settings.image_model,
            "image_fallback_model": settings.image_fallback_model,
            "video_model": settings.video_model,
            "supports_image": bool(settings.siliconflow_api_key),
            "supports_image_to_video": bool(
                settings.video_generation_enabled
                and settings.siliconflow_api_key
                and settings.video_model
            ),
        }
