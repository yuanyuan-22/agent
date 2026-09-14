from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from forge.agents.nodes import (
    director_node,
    pack_assets_node,
    review_node,
    write_node,
)
from forge.config import settings
from forge.store import get_job, update_job


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_state(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise RuntimeError("job not found")
    run_dir = Path(job.get("run_dir") or (settings.work_dir / job_id))
    state = {
        "job_id": job_id,
        "run_dir": str(run_dir),
        "style": job.get("style") or "",
        "target_platforms": job.get("target_platforms") or ["bilibili"],
        "video": _read_json(run_dir / "source_video.json"),
        "dna": _read_json(run_dir / "dna.json"),
        "ideas": _read_json(run_dir / "ideas.json"),
        "selected_idea": _read_json(run_dir / "selected_idea.json"),
        "script": _read_json(run_dir / "script.json"),
        "storyboard": _read_json(run_dir / "storyboard.json"),
        "review": _read_json(run_dir / "review.json"),
        "rewrite_count": 0,
        "manual_review": bool(job.get("manual_review")),
    }
    if not state["selected_idea"] and state["ideas"]:
        state["selected_idea"] = max(
            state["ideas"],
            key=lambda item: float(item.get("total_score") or 0),
        )
    return state


def approve_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise RuntimeError("job not found")
    if not job.get("asset_pack_path"):
        raise RuntimeError("asset pack is not ready")
    update_job(
        job_id,
        status="approved",
        review_status="approved",
        manual_review=False,
    )
    return get_job(job_id) or {}


def reject_job(job_id: str, feedback: str = "") -> dict:
    state = _load_state(job_id)
    if not state.get("dna") or not state.get("selected_idea"):
        raise RuntimeError("planning context is incomplete")
    state["feedback"] = feedback or "请严格保持原内容主题，并删除缺少来源支撑的事实。"
    for _ in range(2):
        state["rewrite_count"] = int(state.get("rewrite_count") or 0) + 1
        state.update(write_node(state))
        state.update(director_node(state))
        state.update(review_node(state))
        if state.get("decision") == "pack_assets":
            break
        issues = "；".join((state.get("review") or {}).get("issues") or [])
        state["feedback"] = issues or state["feedback"]
    state.update(pack_assets_node(state))
    return state


def edit_job(job_id: str, *, script: dict | None = None,
             storyboard: dict | None = None) -> dict:
    state = _load_state(job_id)
    if script is not None:
        state["script"] = script
        _write_json(Path(state["run_dir"]) / "script.json", script)
    if storyboard is not None:
        state["storyboard"] = storyboard
        _write_json(Path(state["run_dir"]) / "storyboard.json", storyboard)
    elif script is not None:
        state.update(director_node(state))
    if not state.get("script") or not state.get("storyboard"):
        raise RuntimeError("script and storyboard are required")
    state.update(review_node(state))
    state.update(pack_assets_node(state))
    return state
