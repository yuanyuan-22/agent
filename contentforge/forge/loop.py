from __future__ import annotations

from forge import experience as exp_store
from forge.metrics import sync_job
from forge.replier import build_insights
from forge.store import add_event, get_job, list_metrics, mark_published, update_job


def _metric_values(row: dict | None) -> dict:
    if row:
        return {k: row.get(k, 0) for k in ("view", "like", "coin", "share", "favorite", "danmaku", "reply")}
    return {}


def publish_job(job_id: str, own_bvid: str, platform: str = "bilibili",
                url: str = "") -> dict:
    ok = mark_published(job_id, own_bvid, platform=platform, url=url)
    if not ok:
        raise ValueError(f"任务不存在: {job_id}")
    add_event(job_id, "publish", f"标记已发布 platform={platform} id={own_bvid}")
    if platform == "bilibili":
        row = sync_job(job_id)
        add_event(job_id, "metric", f"首次数据回流: 播放 {row['view']}")
        _learn(job_id, row)
    return get_job(job_id) or {}


def sync_and_learn(job_id: str) -> dict:
    row = sync_job(job_id)
    add_event(job_id, "metric", f"数据回流: 播放 {row['view']} 赞 {row['like']} 评论 {row['reply']}")
    _learn(job_id, row)
    return row


def import_metrics(job_id: str, stats: dict, platform: str = "manual") -> dict:
    from forge.store import record_metric

    if get_job(job_id) is None:
        raise ValueError(f"任务不存在: {job_id}")
    row = record_metric(job_id, stats, platform=platform)
    add_event(job_id, "metric",
              f"导入 {platform} 数据: 播放 {row.get('view', 0)} 赞 {row.get('like', 0)}")
    _learn(job_id, row)
    return row


def _learn(job_id: str, metric_row: dict | None = None) -> dict | None:
    job = get_job(job_id)
    if job is None or not job.get("published"):
        return None
    try:
        insights = build_insights(job)
    except Exception as e:
        add_event(job_id, "error", f"复盘 Agent 失败: {e}")
        return None

    metrics = metric_row or _metric_values(None)
    script_title = (job.get("result") or {}).get("script_title") or job.get("title") or ""
    exp_id = exp_store.add_experience(
        source_job_id=job_id,
        topic="可继续方向" if insights.get("keep_topic", True) else "建议收敛方向",
        title=script_title,
        insights="\n".join(insights.get("lessons", [])),
        metrics=metrics,
        score=10.0 if insights.get("keep_topic", True) else 5.0,
    )
    update_job(job_id, status="learned")
    add_event(job_id, "learn", f"经验已沉淀到经验库(#{exp_id})",
              {"verdict": insights.get("verdict", ""), "lessons": insights.get("lessons", [])})
    return insights
