from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class ContentInsight:
    topic: str = ""
    audience: str = ""
    emotion: str = ""
    hook_formula: str = ""
    structure: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    visual_motifs: List[str] = field(default_factory=list)
    comments_needs: List[str] = field(default_factory=list)
    why_viral: str = ""
    platform_signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IdeaCandidate:
    angle: str
    title: str
    hook: str
    differentiation: float = 0.0
    visual_score: float = 0.0
    platform_fit: float = 0.0
    safety_score: float = 0.0
    total_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StoryboardScene:
    shot_id: int
    purpose: str = "body"
    narration: str = ""
    caption: str = ""
    duration_hint: float = 8.0
    importance: float = 0.5
    visual_prompt: str = ""
    video_prompt: str = ""
    motion: str = "slow_zoom"
    asset_policy: str = "generate_image"
    transition: str = "fade"
    on_screen_text: str = ""
    show_character: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CharacterBible:
    character_id: str = "host_default"
    name: str = "小知"
    description: str = "flat vector tech presenter, friendly, consistent appearance"
    style_prompt: str = "flat vector illustration, clean lines, dark blue and cyan palette"
    seed: int = 20260910
    base_image_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationRequest:
    kind: str
    prompt: str
    aspect_ratio: str = "9:16"
    seed: int | None = None
    image_path: str = ""
    duration_sec: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    ok: bool
    kind: str
    provider: str = ""
    model: str = ""
    path: str = ""
    prompt: str = ""
    seed: int | None = None
    latency_ms: int = 0
    cost: float = 0.0
    error: str = ""
    fallback_from: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
