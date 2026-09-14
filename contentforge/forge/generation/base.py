from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from forge.content_plan import GenerationRequest, GenerationResult


class GenerationProvider(ABC):
    name = "base"

    @abstractmethod
    def generate_image(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    def generate_video(self, request: GenerationRequest, work_dir: Path) -> GenerationResult:
        raise NotImplementedError
