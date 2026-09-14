from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from forge.channels.bilibili import parse_bvid
from forge.store import add_event, get_job, mark_published, update_job

PLATFORM_META = {
    "bilibili": {
        "name": "B站",
        "upload_url": "https://member.bilibili.com/platform/upload/video/frame",
    },
    "douyin": {
        "name": "抖音",
        "upload_url": "https://creator.douyin.com/creator-micro/content/upload",
    },
    "kuaishou": {
        "name": "快手",
        "upload_url": "https://cp.kuaishou.com/article/publish/video",
    },
    "xiaohongshu": {
        "name": "小红书",
        "upload_url": "https://creator.xiaohongshu.com/publish/publish",
    },
}


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def prepare_publish_package(job_id: str,
                            platforms: List[str] | None = None) -> Dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"任务不存在: {job_id}")
    run_dir = Path(job.get("run_dir") or "")
    result = job.get("result") or {}
    media = result.get("media") or {}
    script = _read_json(run_dir / "script.json")
    pack = _read_json(run_dir / "publish_pack.json")
    generation = _read_json(run_dir / "media" / "generation_manifest.json")

    targets = [p.strip() for p in (platforms or job.get("target_platforms") or ["bilibili"]) if p and p.strip()]
    if not targets:
        targets = ["bilibili"]
    out_dir = run_dir / "publish"
    out_dir.mkdir(parents=True, exist_ok=True)
    packages = {}
    for platform in targets:
        meta = PLATFORM_META.get(platform, {"name": platform, "upload_url": ""})
        item = {
            "platform": platform,
            "platform_name": meta["name"],
            "upload_url": meta["upload_url"],
            "video_path": media.get("video") or pack.get("video") or "",
            "cover_path": media.get("cover") or pack.get("cover") or "",
            "captions_path": media.get("captions") or "",
            "manifest_path": media.get("manifest") or "",
            "generation_manifest_path": media.get("generation_manifest") or "",
            "visual_review_path": media.get("visual_review") or "",
            "generation_total_cost": generation.get("total_cost", 0),
            "title": script.get("title") or pack.get("title") or "",
            "description": script.get("description") or pack.get("description") or "",
            "tags": script.get("tags") or pack.get("tags") or [],
            "publish_mode": "human_in_the_loop",
        }
        packages[platform] = item
        (out_dir / f"{platform}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / f"{platform}.txt").write_text(
            "\n".join([
                f"标题：{item['title']}",
                f"标签：{' '.join(item['tags'])}",
                "",
                item["description"],
            ]),
            encoding="utf-8",
        )

    add_event(job_id, "publish_prepare", "已生成多平台发布包",
              {"platforms": targets})
    update_job(job_id, status="publish_ready")
    return {"job_id": job_id, "platforms": packages, "package_dir": str(out_dir)}


def mark_platform_published(job_id: str, platform: str,
                            external_id: str, url: str = "") -> Dict[str, Any]:
    platform = (platform or "bilibili").strip()
    raw_id = (external_id or url or "").strip()
    if not raw_id:
        raise ValueError("请填写发布后的视频 ID、BV号或视频链接")
    if platform == "bilibili":
        external_id = parse_bvid(raw_id)
    else:
        external_id = raw_id
    if not mark_published(job_id, external_id, platform=platform, url=url):
        raise ValueError(f"任务不存在: {job_id}")
    add_event(job_id, "publish", f"已记录 {platform} 发布: {external_id}",
              {"platform": platform, "external_id": external_id, "url": url})
    return get_job(job_id) or {}
