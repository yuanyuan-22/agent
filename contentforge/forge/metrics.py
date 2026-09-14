from __future__ import annotations

from forge.channels.bilibili import BiliClient, BiliError
from forge.store import get_job, record_metric


def fetch_own_stat(bvid: str) -> dict:
    client = BiliClient()
    try:
        info = client.view(bvid)
        if not info:
            raise BiliError(f"视频不存在: {bvid}")
        return (info.get("stat") or {})
    finally:
        client.close()


def sync_job(job_id: str) -> dict | None:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"任务不存在: {job_id}")
    if not job.get("published") or not job.get("own_bvid"):
        raise ValueError(f"任务 {job_id} 尚未标记已发布(缺少 own_bvid)")
    stat = fetch_own_stat(job["own_bvid"])
    row = record_metric(job_id, stat)
    return row


def sync_platform_job(job_id: str, platform: str) -> dict:
    """B站自动拉公开 stat；其他平台尝试公开页解析，失败后由调用方转手动录入。"""
    platform = (platform or "bilibili").strip()
    if platform == "bilibili":
        row = sync_job(job_id)
        return row or {}

    job = get_job(job_id)
    if job is None:
        raise ValueError(f"任务不存在: {job_id}")
    record = (job.get("publish_records") or {}).get(platform) or {}
    url = (record.get("url") or record.get("external_id") or "").strip()
    if not url:
        raise ValueError(f"{platform} 尚未记录发布链接/ID")
    if not url.startswith("http"):
        raise ValueError(f"{platform} 当前只有 ID，无法自动拉取公开指标，请手动录入")

    from forge.channels.registry import get_adapter

    source = get_adapter(platform).fetch(url)
    stats = dict(source.stats or {})
    if not stats or not any(float(stats.get(k) or 0) for k in ("view", "like", "reply", "share", "favorite")):
        raise ValueError(f"{platform} 公开页未解析到指标，请手动录入")
    return record_metric(job_id, stats, platform=platform)
