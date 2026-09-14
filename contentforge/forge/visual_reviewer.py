from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def review_visuals(scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
    issues: List[str] = []
    fallbacks = 0
    generated = 0
    video_scenes = 0
    fingerprints = []

    for index, scene in enumerate(scenes, start=1):
        asset = scene.get("asset") or {}
        kind = asset.get("kind") or "card"
        provider = str(asset.get("provider") or "")
        policy = str(scene.get("asset_policy") or "")
        prompt = str(scene.get("visual_prompt") or scene.get("video_prompt") or "")

        if not prompt and policy.startswith("generate"):
            issues.append(f"第{index}镜缺少视觉提示词")
        if policy == "generate_video":
            video_scenes += 1
            if kind != "video":
                fallbacks += 1
                issues.append(f"第{index}镜图生视频失败，已降级为{kind}")
        if provider and provider not in ("pexels", "local"):
            generated += 1
        if kind == "card":
            fallbacks += 1
        if asset.get("fingerprint"):
            fingerprints.append(asset["fingerprint"])
        if scene.get("show_character") and not (scene.get("character") or {}).get("base_image_path"):
            issues.append(f"第{index}镜需要讲解员但角色资产缺失")

    duplicates = [key for key, count in Counter(fingerprints).items() if count > 1]
    if duplicates:
        issues.append("存在重复素材，请检查素材去重")

    penalty = min(8.0, len(issues) * 0.8 + fallbacks * 0.4)
    score = round(max(0.0, 10.0 - penalty), 2)
    return {
        "pass": score >= 6.0,
        "score": score,
        "scene_count": len(scenes),
        "generated_scenes": generated,
        "video_scenes": video_scenes,
        "fallback_count": fallbacks,
        "issues": issues,
    }
