from __future__ import annotations

import json
from typing import Any, Dict, List

from forge.llm import chat_json

IDEATION_SYSTEM = """你是短视频选题策划。根据「内容洞察」，生成 3 个差异明显的原创角度。
只输出 JSON：
{
  "ideas": [
    {
      "angle": "选题角度",
      "title": "标题，不超过22字",
      "hook": "前3秒钩子",
      "differentiation": 0-10,
      "visual_score": 0-10,
      "platform_fit": 0-10,
      "safety_score": 0-10
    }
  ]
}
要求：
1. 3 个角度必须围绕原内容的同一主题、人物、场景和核心信息展开，不能换题，不能跨到无关领域。
2. 角度之间不能只是换标题；必须适合用动画画面表达，且不照搬原视频表达。
3. 如果 insight.topic 为“信息不足”，必须返回空 ideas，不得自行编造选题。"""


def _score(idea: Dict[str, Any]) -> float:
    return (
        float(idea.get("differentiation") or 0) * 0.3
        + float(idea.get("visual_score") or 0) * 0.3
        + float(idea.get("platform_fit") or 0) * 0.25
        + float(idea.get("safety_score") or 0) * 0.15
    )


def generate_ideas(insight: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        data = chat_json(
            IDEATION_SYSTEM,
            json.dumps({"insight": insight}, ensure_ascii=False),
            temperature=0.7,
        )
        ideas = data.get("ideas") or []
    except Exception:
        ideas = []
    if not ideas:
        topic = insight.get("topic") or "热门话题"
        if topic == "信息不足":
            return []
        ideas = [{
            "angle": topic,
            "title": f"重新理解{topic}",
            "hook": f"关于{topic}，大多数人忽略了一个关键点。",
            "differentiation": 6,
            "visual_score": 6,
            "platform_fit": 6,
            "safety_score": 8,
        }]
    for idea in ideas:
        idea["total_score"] = round(_score(idea), 2)
    ideas.sort(key=lambda item: float(item.get("total_score") or 0), reverse=True)
    return ideas


def select_best(ideas: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not ideas:
        raise ValueError("source context is insufficient; no grounded ideas")
    return max(ideas, key=lambda item: float(item.get("total_score") or 0))
