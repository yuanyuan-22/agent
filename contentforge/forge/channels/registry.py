from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .base import ChannelAdapter, ChannelError, SourceVideo
from .bilibili import BilibiliAdapter, parse_bvid
from .douyin import DouyinAdapter
from .kuaishou import KuaishouAdapter
from .manual import ManualAdapter
from .share_page import extract_first_url
from .xiaohongshu import XiaohongshuAdapter

_ADAPTERS: list[ChannelAdapter] = [
    BilibiliAdapter(),
    DouyinAdapter(),
    KuaishouAdapter(),
    XiaohongshuAdapter(),
]

PLATFORMS = ("bilibili", "douyin", "kuaishou", "xiaohongshu")


def get_adapter(url_or_platform: str) -> ChannelAdapter:
    value = (url_or_platform or "").strip()
    extracted = extract_first_url(value)
    if extracted:
        value = extracted
    for adapter in _ADAPTERS:
        if adapter.platform == value:
            return adapter
    for adapter in _ADAPTERS:
        if adapter.match(value):
            return adapter
    if "bilibili" in value.lower() or value.upper().startswith("BV"):
        return _ADAPTERS[0]
    raise ChannelError(f"无法识别渠道: {url_or_platform}")


def fetch_source(channel: str, source: str, manual: Dict[str, Any] | None = None) -> SourceVideo:
    if manual:
        return ManualAdapter(channel or str(manual.get("platform") or "manual"), manual).fetch(source)
    adapter = get_adapter(channel or source)
    return adapter.fetch(source)


def trending(platform: str, limit: int = 10) -> List[Dict[str, Any]]:
    adapter = get_adapter(platform)
    try:
        return adapter.trending(limit=limit)
    except NotImplementedError:
        return []
