from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def build_manifest(script: Dict[str, Any], scenes: List[Dict[str, Any]],
                   *, out_dir: Path, size: tuple[int, int], fps: int) -> Dict[str, Any]:
    current = 0.0
    rows = []
    for index, scene in enumerate(scenes, start=1):
        duration = float(scene.get("duration") or 0)
        caption = str(scene.get("caption") or scene.get("text") or "")
        asset = scene.get("asset") or {}
        rows.append({
            "index": index,
            "start": round(current, 3),
            "end": round(current + duration, 3),
            "duration": round(duration, 3),
            "heading": scene.get("heading") or "",
            "caption": caption,
            "voiceover": scene.get("text") or "",
            "visual_type": scene.get("visual_type") or ("card" if not asset else asset.get("kind")),
            "asset": asset,
        })
        current += duration
    return {
        "title": script.get("title") or "",
        "cover_text": script.get("cover_text") or "",
        "size": list(size),
        "fps": fps,
        "duration": round(current, 3),
        "scene_count": len(rows),
        "scenes": rows,
    }


def write_manifest(manifest: Dict[str, Any], out_dir: Path) -> Path:
    path = out_dir / "video_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_srt(manifest: Dict[str, Any], out_dir: Path) -> Path:
    path = out_dir / "captions.srt"
    blocks = []
    for scene in manifest.get("scenes") or []:
        caption = str(scene.get("caption") or "").strip()
        if not caption:
            continue
        start = _ts(float(scene.get("start") or 0))
        end = _ts(float(scene.get("end") or 0))
        blocks.append(f"{scene.get('index')}\n{start} --> {end}\n{caption}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def build_generation_manifest(scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    total_cost = 0.0
    for index, scene in enumerate(scenes, start=1):
        asset = scene.get("asset") or {}
        meta = asset.get("meta") or {}
        cost = float(meta.get("cost") or 0)
        total_cost += cost
        rows.append({
            "scene": index,
            "provider": asset.get("provider") or "fallback",
            "model": asset.get("author") or "",
            "kind": asset.get("kind") or "card",
            "query": asset.get("query") or "",
            "path": asset.get("path") or "",
            "cost": cost,
            "latency_ms": int(meta.get("latency_ms") or 0),
            "fallback_from": meta.get("fallback_from") or "",
            "error": meta.get("error") or "",
        })
    return {
        "total_cost": round(total_cost, 6),
        "scene_count": len(rows),
        "scenes": rows,
    }


def _ts(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
