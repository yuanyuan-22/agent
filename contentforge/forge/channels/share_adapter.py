from __future__ import annotations

import hashlib
import re
from typing import Iterable

from .base import ChannelAdapter, ChannelError, SourceVideo
from .share_page import extract_first_url, fetch_page, normalize_page, resolve_share_url


class SharePageAdapter(ChannelAdapter):
    """公开分享页 best-effort 解析器；不携带 Cookie、不模拟登录。"""

    url_patterns: tuple[re.Pattern[str], ...] = ()

    def match(self, url: str) -> bool:
        candidate = extract_first_url(url) or (url or "")
        return any(pattern.search(candidate) for pattern in self.url_patterns)

    def resolve_share_url(self, url: str) -> str:
        return resolve_share_url(url)

    def fetch(self, url: str, *, with_transcript: bool = True) -> SourceVideo:
        source_url = extract_first_url(url) or url
        final_url, html = fetch_page(source_url)
        payload = normalize_page(final_url, html, self.platform)
        source_id = _extract_source_id(final_url)
        transcript = str(payload.get("transcript") or payload.get("description") or "")
        return SourceVideo(
            platform=self.platform,
            source_id=source_id,
            source_url=final_url,
            title=str(payload.get("title") or ""),
            author=str(payload.get("author") or ""),
            description=str(payload.get("description") or ""),
            cover_url=str(payload.get("cover_url") or ""),
            duration_sec=float(payload.get("duration_sec") or 0),
            stats=dict(payload.get("stats") or {}),
            transcript=transcript,
            transcript_mode="page" if transcript else "none",
            media_url=str(payload.get("media_url") or ""),
            raw=payload,
        )


def _extract_source_id(url: str) -> str:
    for pattern in (
        r"/(?:video|note|item|photo|short-video)/([A-Za-z0-9_-]+)",
        r"[?&](?:id|item_id|note_id|aweme_id)=([A-Za-z0-9_-]+)",
    ):
        match = re.search(pattern, url or "")
        if match:
            return match.group(1)
    return hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:16]
