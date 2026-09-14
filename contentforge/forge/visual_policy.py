from __future__ import annotations

from typing import Any, Dict, List


GENERATION_MODES = {
    "low_cost": {"images": 6, "videos": 1, "max_scenes": 6},
    "balanced": {"images": 12, "videos": 3, "max_scenes": 8},
    "high_quality": {"images": 18, "videos": 5, "max_scenes": 8},
}


def normalize_mode(mode: str) -> str:
    value = (mode or "balanced").strip().lower()
    return value if value in GENERATION_MODES else "balanced"


def choose_video_scene_indexes(scenes: List[Dict[str, Any]], mode: str = "balanced") -> List[int]:
    """根据镜头目的和重要性选择 1-3 个图生视频镜头。"""
    cfg = GENERATION_MODES[normalize_mode(mode)]
    limit = int(cfg["videos"])
    ranked = []
    for index, scene in enumerate(scenes):
        purpose = str(scene.get("purpose") or "body")
        importance = float(scene.get("importance") or 0.5)
        bonus = 0.3 if purpose in ("hook", "reveal", "cta") else 0.0
        ranked.append((importance + bonus, index))
    ranked.sort(reverse=True)
    return sorted(index for _score, index in ranked[:limit])


def apply_visual_policy(scenes: List[Dict[str, Any]], mode: str = "balanced") -> List[Dict[str, Any]]:
    mode = normalize_mode(mode)
    cfg = GENERATION_MODES[mode]
    selected = set(choose_video_scene_indexes(scenes, mode))
    out = []
    image_count = 0
    video_count = 0
    for index, scene in enumerate(scenes[: int(cfg["max_scenes"])]):
        row = dict(scene)
        wants_video = index in selected and video_count < int(cfg["videos"])
        visual_type = (row.get("visual_type") or "").strip().lower()
        if wants_video:
            row["asset_policy"] = "generate_video"
            row["visual_type"] = "video"
            video_count += 1
        elif image_count < int(cfg["images"]):
            row["asset_policy"] = row.get("asset_policy") or "generate_image"
            row["visual_type"] = row.get("visual_type") or "image"
            image_count += 1
        else:
            row["asset_policy"] = "card"
            row["visual_type"] = "card"
        out.append(row)
    return out
