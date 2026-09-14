from __future__ import annotations

from typing import Any, Dict

from .base import ChannelAdapter, SourceVideo


class ManualAdapter(ChannelAdapter):
    """无法自动解析时的手动回退，不发起网络请求。"""

    platform = "manual"

    def __init__(self, platform: str, metadata: Dict[str, Any] | None = None):
        self.platform = platform or "manual"
        self.metadata = metadata or {}

    def match(self, url: str) -> bool:
        return False

    def fetch(self, url: str, *, with_transcript: bool = True) -> SourceVideo:
        meta = dict(self.metadata)
        return SourceVideo(
            platform=self.platform,
            source_id=str(meta.get("source_id") or url or "manual"),
            source_url=str(meta.get("source_url") or url or ""),
            title=str(meta.get("title") or ""),
            author=str(meta.get("author") or ""),
            description=str(meta.get("description") or ""),
            cover_url=str(meta.get("cover_url") or ""),
            duration_sec=float(meta.get("duration_sec") or 0),
            stats=dict(meta.get("stats") or {}),
            transcript=str(meta.get("transcript") or meta.get("description") or ""),
            transcript_mode=str(meta.get("transcript_mode") or ("manual" if meta else "none")),
            media_url=str(meta.get("media_url") or ""),
            raw={"manual": meta},
        )
