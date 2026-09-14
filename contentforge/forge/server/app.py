from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import Body, FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from forge import experience as exp_store
from forge.asset_pack import load_asset_pack
from forge.channels.registry import get_adapter
from forge.channels.share_page import extract_first_url, parse_share_text
from forge.graph import new_job, render_approved_job, run_job_graph
from forge.job_flow import approve_job, edit_job, reject_job
from forge.loop import import_metrics, publish_job, sync_and_learn
from forge.metrics import sync_platform_job
from forge.publish import mark_platform_published, prepare_publish_package
from forge.scheduler import start_scheduler, stop_scheduler
from forge.store import (add_event, events_after, get_job, init_db, list_experiences,
                         list_jobs, list_metrics, list_source_items,
                         update_job, upsert_source_item)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


init_db()

app = FastAPI(title="ContentForge Console", version="0.2", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"


def _worker(job_id: str, source: str, style: str, channel: str = "auto",
            target_platforms: list[str] | None = None,
            manual: dict | None = None,
            visual_style: str = "tech_infographic",
            generation_mode: str = "balanced",
            character_id: str = "host_default") -> None:
    try:
        run_job_graph(job_id, source, style, channel=channel,
                      target_platforms=target_platforms, manual=manual,
                      visual_style=visual_style,
                      generation_mode=generation_mode,
                      character_id=character_id)
    except Exception:
        pass


def _render_worker(job_id: str) -> None:
    try:
        render_approved_job(job_id)
    except Exception as exc:
        add_event(job_id, "error", f"渲染失败: {exc}")
        update_job(job_id, status="failed", error=str(exc)[:500])


@app.post("/api/jobs")
def create_job(body: dict = Body(...)):
    source_input = (body.get("source") or "").strip()
    source = extract_first_url(source_input) or source_input
    style = (body.get("style") or "").strip()
    channel = (body.get("channel") or "auto").strip()
    target_platforms = body.get("target_platforms") or ["bilibili"]
    manual = body.get("manual") or {}
    if not manual:
        parsed_share = parse_share_text(source_input)
        if parsed_share:
            parsed_share["fallback_only"] = True
            try:
                parsed_share["platform"] = (
                    get_adapter(source).platform if channel in ("", "auto") else channel
                )
            except Exception:
                parsed_share["platform"] = channel if channel not in ("", "auto") else "manual"
            manual = parsed_share
    visual_style = (body.get("visual_style") or "tech_infographic").strip()
    generation_mode = (body.get("generation_mode") or "balanced").strip()
    character_id = (body.get("character_id") or "host_default").strip()
    if isinstance(target_platforms, str):
        target_platforms = [x.strip() for x in target_platforms.split(",") if x.strip()]
    if not source:
        return {"error": "source required"}
    job_id = new_job(source, style, channel=channel,
                     target_platforms=target_platforms,
                     visual_style=visual_style,
                     generation_mode=generation_mode,
                     character_id=character_id)
    t = threading.Thread(target=_worker,
                         args=(job_id, source, style, channel, target_platforms, manual,
                               visual_style, generation_mode, character_id),
                         daemon=True)
    t.start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs")
def all_jobs():
    return {"jobs": list_jobs()}


@app.get("/api/jobs/{job_id}")
def one_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        return {"error": "not found"}
    return job


@app.get("/api/jobs/{job_id}/assets")
def job_assets(job_id: str):
    job = get_job(job_id)
    if job is None:
        return {"ok": False, "error": "not found"}
    pack = load_asset_pack(job.get("asset_pack_path") or "")
    if pack is None:
        return {"ok": False, "error": "asset pack is not ready"}
    return {"ok": True, "asset_pack": pack}


@app.post("/api/jobs/{job_id}/review")
def review_job(job_id: str, body: dict = Body(...)):
    action = (body.get("action") or "").strip().lower()
    try:
        if action == "approve":
            approve_job(job_id)
        elif action == "reject":
            reject_job(job_id, str(body.get("feedback") or ""))
        elif action == "edit":
            edit_job(
                job_id,
                script=body.get("script"),
                storyboard=body.get("storyboard"),
            )
        else:
            return {"ok": False, "error": "action must be approve/reject/edit"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "job": get_job(job_id)}


@app.post("/api/jobs/{job_id}/render")
def render_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        return {"ok": False, "error": "not found"}
    if job.get("review_status") != "approved":
        return {"ok": False, "error": "请先审核通过内容资产包"}
    update_job(job_id, status="rendering", error="")
    add_event(job_id, "step", "用户已确认，开始可选视频渲染")
    threading.Thread(
        target=_render_worker,
        args=(job_id,),
        daemon=True,
    ).start()
    return {"ok": True, "status": "rendering"}


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    after = int(request.query_params.get("last", 0))

    async def gen():
        last = after
        idle = 0
        while True:
            if await request.is_disconnected():
                break
            evs = events_after(job_id, last)
            for ev in evs:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                last = ev["id"]
            job = get_job(job_id)
            if job is None:
                yield "event: close\ndata: {}\n\n"
                break
            if evs:
                idle = 0
            else:
                idle += 1
            if job.get("status") in ("done", "failed") and idle >= 2:
                yield "event: close\ndata: {}\n\n"
                break
            await _asleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _asleep(sec: float) -> None:
    import asyncio
    await asyncio.sleep(sec)


@app.post("/api/jobs/{job_id}/publish")
def do_publish(job_id: str, body: dict = Body(...)):
    bvid = (body.get("bvid") or "").strip()
    if not bvid:
        return {"error": "bvid required"}
    try:
        job = publish_job(job_id, bvid)
        return {"ok": True, "job": job}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/jobs/{job_id}/sync")
def do_sync(job_id: str):
    try:
        row = sync_and_learn(job_id)
        return {"ok": True, "metric": row}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/jobs/{job_id}/metrics")
def job_metrics(job_id: str):
    return {"metrics": list_metrics(job_id)}


@app.get("/api/experience")
def experience_search(q: str = "", top_k: int = 3):
    if not q.strip():
        return {"items": list_experiences(limit=20)}
    hits = exp_store.search(q, top_k=top_k)
    return {"items": hits}


@app.post("/api/sources/import")
def import_sources(body: dict = Body(...)):
    raw_items = body.get("items") or []
    urls = body.get("urls") or []
    if isinstance(urls, str):
        urls = [line.strip() for line in urls.splitlines() if line.strip()]
    items = list(raw_items)
    items.extend({"url": url} for url in urls)
    imported = []
    for item in items:
        url = (item.get("url") or item.get("source") or "").strip()
        if not url:
            continue
        try:
            requested = (item.get("platform") or "").strip()
            adapter = get_adapter(url if requested in ("", "auto") else requested)
            source = adapter.fetch(url)
            row = upsert_source_item(
                source.platform,
                url,
                status="parsed",
                title=source.title,
                payload=source.to_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            platform = (item.get("platform") or "manual").strip()
            row = upsert_source_item(
                platform,
                url,
                status="manual_required",
                title=item.get("title") or "",
                payload={**item, "error": str(exc)},
            )
        imported.append(row)
    return {"items": imported}


@app.get("/api/sources/trending")
def source_trending(platform: str = "bilibili", limit: int = 10):
    if platform == "bilibili":
        try:
            adapter = get_adapter(platform)
            return {"platform": platform, "items": adapter.trending(limit=limit)}
        except Exception as exc:  # noqa: BLE001
            return {"platform": platform, "items": [], "error": str(exc)}
    return {
        "platform": platform,
        "items": list_source_items(platform=platform, limit=limit),
    }


@app.post("/api/jobs/{job_id}/publish/prepare")
def prepare_publish(job_id: str, body: dict = Body(default={})):
    try:
        platforms = body.get("platforms") or []
        if isinstance(platforms, str):
            platforms = [x.strip() for x in platforms.split(",") if x.strip()]
        return {"ok": True, "package": prepare_publish_package(job_id, platforms=platforms)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.post("/api/jobs/{job_id}/publish/mark")
def mark_publish(job_id: str, body: dict = Body(...)):
    try:
        platform = (body.get("platform") or "bilibili").strip()
        external_id = (body.get("external_id") or body.get("bvid") or "").strip()
        url = (body.get("url") or "").strip()
        job = mark_platform_published(job_id, platform, external_id, url)
        warning = ""
        if platform == "bilibili":
            try:
                sync_and_learn(job_id)
                job = get_job(job_id) or job
            except Exception as exc:  # noqa: BLE001
                warning = f"发布已记录，但 B站数据回流失败: {exc}"
        return {"ok": True, "job": job, "warning": warning}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.post("/api/jobs/{job_id}/metrics/import")
def import_job_metrics(job_id: str, body: dict = Body(...)):
    try:
        platform = (body.get("platform") or "manual").strip()
        stats = body.get("stats") or {
            key: int(body.get(key) or 0)
            for key in ("view", "like", "coin", "share", "favorite", "danmaku", "reply")
        }
        row = import_metrics(job_id, stats, platform=platform)
        return {"ok": True, "metric": row}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.post("/api/jobs/{job_id}/metrics/sync")
def sync_job_metrics(job_id: str, body: dict = Body(...)):
    try:
        platform = (body.get("platform") or "bilibili").strip()
        row = sync_platform_job(job_id, platform)
        add_event(job_id, "metric",
                  f"{platform} 数据同步: 播放 {row.get('view', 0)} 赞 {row.get('like', 0)}")
        return {"ok": True, "metric": row}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "manual_required": True}


@app.get("/api/generation/capabilities")
def generation_capabilities():
    from forge.generation.manager import GenerationManager

    return GenerationManager().capabilities()


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8017)
