from __future__ import annotations

import uuid
import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from forge.agents.nodes import (
    JobState,
    analyze_node,
    director_node,
    fetch_node,
    ideate_node,
    pack_assets_node,
    producer_node,
    pack_node,
    review_node,
    write_node,
)
from forge.config import settings
from forge.store import add_event, create_job, get_job, init_db, update_job


def route_after_review(state: JobState) -> str:
    return state.get("decision", "pack_assets")


def build_graph(checkpointer=None):
    g = StateGraph(JobState)
    g.add_node("fetch", fetch_node)
    g.add_node("analyze", analyze_node)
    g.add_node("ideate", ideate_node)
    g.add_node("write", write_node)
    g.add_node("director", director_node)
    g.add_node("review", review_node)
    g.add_node("pack_assets", pack_assets_node)

    g.add_edge(START, "fetch")
    g.add_edge("fetch", "analyze")
    g.add_edge("analyze", "ideate")
    g.add_edge("ideate", "write")
    g.add_edge("write", "director")
    g.add_edge("director", "review")
    g.add_conditional_edges("review", route_after_review,
                            {"pack_assets": "pack_assets", "writer": "write"})
    g.add_edge("pack_assets", END)
    return g.compile(checkpointer=checkpointer)


_saver = None


def _checkpointer():
    global _saver
    if _saver is not None:
        return _saver
    try:
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(str(settings.data_dir / "langgraph.sqlite"),
                               check_same_thread=False)
        _saver = SqliteSaver(conn)
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver

        _saver = MemorySaver()
    return _saver


def _initial_state(job_id: str, source: str, style: str,
                   channel: str = "auto",
                   target_platforms: list[str] | None = None,
                   manual: dict | None = None,
                   visual_style: str = "tech_infographic",
                   generation_mode: str = "balanced",
                   character_id: str = "host_default") -> dict:
    return {
        "job_id": job_id,
        "source": source,
        "channel": channel,
        "target_platforms": target_platforms or ["bilibili"],
        "manual": manual or {},
        "visual_style": visual_style,
        "generation_mode": generation_mode,
        "character_id": character_id,
        "run_dir": str(settings.work_dir / job_id),
        "style": style,
        "rewrite_count": 0,
        "decision": "pack_assets",
        "manual_review": False,
    }


def run_job_graph(job_id: str, source: str, style: str = "",
                  channel: str = "auto",
                  target_platforms: list[str] | None = None,
                  manual: dict | None = None,
                  visual_style: str = "tech_infographic",
                  generation_mode: str = "balanced",
                  character_id: str = "host_default") -> dict:
    init_db()
    graph = build_graph(checkpointer=_checkpointer())
    state = _initial_state(
        job_id, source, style, channel, target_platforms, manual,
        visual_style, generation_mode, character_id,
    )
    config = {"configurable": {"thread_id": job_id}}
    try:
        final = graph.invoke(state, config=config)
        return final
    except Exception as e:
        add_event(job_id, "error", f"任务失败: {e}")
        current = get_job(job_id) or {}
        if current.get("status") != "manual_required":
            update_job(job_id, status="failed", error=str(e)[:500])
        raise


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_approved_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise RuntimeError("job not found")
    if job.get("review_status") != "approved":
        raise RuntimeError("job must be approved before rendering")

    run_dir = Path(job.get("run_dir") or (settings.work_dir / job_id))
    state = {
        "job_id": job_id,
        "run_dir": str(run_dir),
        "script": _read_json(run_dir / "script.json"),
        "storyboard": _read_json(run_dir / "storyboard.json"),
        "video": _read_json(run_dir / "source_video.json"),
        "review": _read_json(run_dir / "review.json"),
        "target_platforms": job.get("target_platforms") or ["bilibili"],
        "manual_review": bool(job.get("manual_review")),
    }
    if not state["script"] or not state["storyboard"]:
        raise RuntimeError("approved asset pack is incomplete")
    produced = producer_node(state)
    state.update(produced)
    pack_node(state)
    return {
        "media": state.get("media") or {},
        "run_dir": str(run_dir),
        "status": "done",
    }


def new_job(source: str, style: str = "", channel: str = "auto",
            target_platforms: list[str] | None = None,
            visual_style: str = "tech_infographic",
            generation_mode: str = "balanced",
            character_id: str = "host_default") -> str:
    job_id = uuid.uuid4().hex[:12]
    create_job(job_id, source, style, channel=channel,
               target_platforms=target_platforms,
               visual_style=visual_style,
               generation_mode=generation_mode,
               character_id=character_id)
    return job_id
