from __future__ import annotations

from typing import Any, Dict, Optional

from forge.channels.bilibili import BiliClient
from forge.channels.manual import ManualAdapter
from forge.channels.registry import get_adapter
from forge.transcript import get_transcript, get_transcript_from_media_url


class SourceContentMissing(RuntimeError):
    pass


def _source_to_video_dict(source) -> Dict[str, Any]:
    return {
        "platform": source.platform,
        "source_id": source.source_id,
        "source_url": source.source_url,
        "bvid": source.source_id if source.platform == "bilibili" else "",
        "cid": (source.raw or {}).get("cid", 0),
        "title": source.title,
        "owner": source.author,
        "desc": source.description,
        "tname": (source.raw or {}).get("tname", ""),
        "pic": source.cover_url,
        "duration": source.duration_sec,
        "stat": source.stats,
        "subtitle_text": source.transcript,
        "transcript_text": source.transcript,
        "transcript_mode": source.transcript_mode,
        "media_url": source.media_url,
        "raw": source.raw,
    }


def fetch_source_video(channel: str, source: str, on_status=None,
                       manual: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """统一抓取入口；B站保留原有 ASR，其他平台使用公开页/媒体 URL 回退。"""
    manual = manual or {}
    manual_override = bool(manual) and not manual.get("fallback_only")
    if manual_override:
        adapter = ManualAdapter(
            channel if channel not in ("", "auto") else str(manual.get("platform") or "manual"),
            manual,
        )
    else:
        adapter = get_adapter(source if channel in ("", "auto") else channel)
    if adapter.platform == "bilibili":
        client = BiliClient()
        try:
            video = client.fetch(source, with_subtitle=True)
            transcript = get_transcript(
                client,
                video,
                on_status=on_status,
            )
        finally:
            client.close()
        video["platform"] = "bilibili"
        video["source_id"] = video.get("bvid") or source
        video["source_url"] = f"https://www.bilibili.com/video/{video.get('bvid') or source}"
        video["transcript_text"] = transcript.get("text", "")
        video["transcript_mode"] = transcript.get("mode", "")
        return video

    try:
        source_video = adapter.fetch(source)
    except Exception as exc:
        if not manual:
            raise SourceContentMissing(
                "平台返回了风控页或无法访问的视频页，且没有可用的原始文案。"
                "请粘贴分享文案或手动补录标题和文案后重试。"
            ) from exc
        source_video = ManualAdapter(
            channel if channel not in ("", "auto") else str(manual.get("platform") or "manual"),
            manual,
        ).fetch(source)
        if source_video.transcript:
            source_video.transcript_mode = "share_text"
    video = _source_to_video_dict(source_video)
    if manual:
        fallback_fields = (
            ("title", "title"),
            ("owner", "author"),
            ("desc", "description"),
            ("transcript_text", "transcript"),
        )
        for target, fallback in fallback_fields:
            if not video.get(target) and manual.get(fallback):
                video[target] = manual[fallback]
    transcript_text = source_video.transcript
    transcript_mode = source_video.transcript_mode
    if not transcript_text and source_video.media_url:
        key = f"{source_video.platform}_{source_video.source_id}"
        transcript = get_transcript_from_media_url(
            source_video.media_url,
            key,
            on_status=on_status,
        )
        transcript_text = transcript.get("text", "")
        transcript_mode = transcript.get("mode", "none")
    if not transcript_text:
        transcript_text = source_video.description
        transcript_mode = transcript_mode or ("page" if transcript_text else "none")
    if not transcript_text and manual:
        transcript_text = manual.get("transcript") or manual.get("description") or ""
        transcript_mode = "share_text" if transcript_text else transcript_mode
    video["transcript_text"] = transcript_text
    video["transcript_mode"] = transcript_mode

    content_signal = " ".join(
        str(video.get(key) or "")
        for key in ("title", "desc", "transcript_text")
    ).strip()
    if len(content_signal) < 8:
        raise SourceContentMissing(
            "没有获取到标题、简介或文案，已停止自动创作。请补齐标题和原始文案后重试。"
        )
    return video
