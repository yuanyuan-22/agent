from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceVideo:
    platform: str
    source_id: str
    source_url: str
    title: str = ""
    author: str = ""
    description: str = ""
    cover_url: str = ""
    duration_sec: float = 0.0
    stats: Dict[str, Any] = field(default_factory=dict)
    transcript: str = ""
    transcript_mode: str = ""
    media_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ChannelError(RuntimeError):
    pass


class ChannelAdapter(ABC):
    platform: str

    @abstractmethod
    def match(self, url: str) -> bool:
        raise NotImplementedError

    def resolve_share_url(self, url: str) -> str:
        return url

    @abstractmethod
    def fetch(self, url: str, *, with_transcript: bool = True) -> SourceVideo:
        raise NotImplementedError

    def normalize(self, raw: Dict[str, Any], url: str = "") -> SourceVideo:
        return SourceVideo(
            platform=self.platform,
            source_id=str(raw.get("source_id") or raw.get("id") or url or "unknown"),
            source_url=url or str(raw.get("source_url") or ""),
            title=str(raw.get("title") or ""),
            author=str(raw.get("author") or raw.get("owner") or ""),
            description=str(raw.get("description") or raw.get("desc") or ""),
            cover_url=str(raw.get("cover_url") or raw.get("pic") or ""),
            duration_sec=float(raw.get("duration_sec") or raw.get("duration") or 0),
            stats=dict(raw.get("stats") or {}),
            transcript=str(raw.get("transcript") or raw.get("transcript_text") or ""),
            transcript_mode=str(raw.get("transcript_mode") or ""),
            media_url=str(raw.get("media_url") or ""),
            raw=raw,
        )

    def trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError(f"{self.platform} 暂不支持趋势榜单")
