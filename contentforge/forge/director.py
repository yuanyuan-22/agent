from __future__ import annotations

import json
from typing import Any, Dict, List

from forge.content_plan import CharacterBible
from forge.llm import chat_json
from forge.visual_policy import apply_visual_policy, normalize_mode

DIRECTOR_SYSTEM = """你是 AI 动画短视频导演。根据原创口播脚本和内容洞察，生成分镜。
只输出 JSON：
{
  "scenes": [
    {
      "shot_id": 1,
      "purpose": "hook/body/reveal/cta",
      "narration": "与脚本对应的口播",
      "caption": "屏幕字幕，不超过36字",
      "duration_hint": 8,
      "importance": 0-1,
      "visual_prompt": "科技信息流动画画面描述，英文优先，具体可视化",
      "video_prompt": "若该镜头生成视频，描述镜头运动和主体动作",
      "motion": "slow_zoom/pan_left/pan_right/parallax",
      "transition": "fade/slide/wipe",
      "on_screen_text": "屏幕上少数关键词，可空",
      "show_character": true或false
    }
  ]
}
要求：5-8 个镜头；前 1 个必须是 hook，最后 1 个必须是 cta；
画面不要出现大段文字；固定讲解员只在合适的镜头出现。"""


STYLE_PROMPTS = {
    "tech_infographic": "dark tech infographic, cyan and blue accents, clean vector shapes, cinematic depth",
    "anime": "modern anime illustration, expressive characters, clean line art",
    "realistic": "cinematic realistic photography, shallow depth of field, natural light",
}


def _fallback_scenes(script: Dict[str, Any]) -> List[Dict[str, Any]]:
    scenes = []
    segments = script.get("segments") or []
    for index, segment in enumerate(segments):
        purpose = "hook" if index == 0 else ("cta" if index == len(segments) - 1 else "body")
        scenes.append({
            "shot_id": index + 1,
            "purpose": purpose,
            "narration": segment.get("text") or "",
            "caption": segment.get("caption") or (segment.get("text") or "")[:36],
            "duration_hint": 8,
            "importance": 0.9 if purpose in ("hook", "cta") else 0.5,
            "visual_prompt": (
                f"{segment.get('heading') or script.get('title') or 'knowledge topic'}, "
                "clean technology infographic scene, no large text"
            ),
            "video_prompt": "",
            "motion": "slow_zoom",
            "transition": "fade",
            "on_screen_text": segment.get("heading") or "",
            "show_character": purpose != "hook",
        })
    return scenes


def build_storyboard(script: Dict[str, Any], insight: Dict[str, Any],
                     *, visual_style: str = "tech_infographic",
                     generation_mode: str = "balanced",
                     character: CharacterBible | None = None) -> Dict[str, Any]:
    character = character or CharacterBible()
    try:
        data = chat_json(
            DIRECTOR_SYSTEM,
            json.dumps({
                "script": script,
                "insight": insight,
                "visual_style": visual_style,
                "style_prompt": STYLE_PROMPTS.get(visual_style, STYLE_PROMPTS["tech_infographic"]),
                "character": character.to_dict(),
            }, ensure_ascii=False),
            temperature=0.5,
        )
        scenes = data.get("scenes") or []
    except Exception:
        scenes = []
    if not scenes:
        scenes = _fallback_scenes(script)
    scenes = apply_visual_policy(scenes, normalize_mode(generation_mode))
    return {
        "visual_style": visual_style,
        "generation_mode": normalize_mode(generation_mode),
        "style_prompt": STYLE_PROMPTS.get(visual_style, STYLE_PROMPTS["tech_infographic"]),
        "character": character.to_dict(),
        "scenes": scenes,
    }
