from __future__ import annotations

import json

from forge.config import settings
from forge.llm import chat_json

WRITER_SYSTEM = """你是短视频原创脚本策划。根据「内容洞察」「已选原创角度」和一份「历史经验库」，
写一条全新的知识/口播动画脚本，不能复述原视频文案。
要求：
1. 必须延续原内容的主题、人物、场景和核心信息，禁止换成无关题材或虚构新故事。
2. 内容必须围绕已选角度重新组织，增加解释、类比、步骤或反常识信息；不得只是同义改写。
3. 开头 3 秒抓人，中段有节奏推进，结尾自然引导点赞/关注。
3. 只输出一个 JSON 对象，schema：
{
  "title": "标题，不超过22字，含钩子",
  "tags": ["标签，最多5个"],
  "cover_text": "封面大字，不超过12字",
  "segments": [
    {
      "heading": "小标题(可空字符串)",
      "text": "一段口语化解说词，60-130字",
      "caption": "该段屏幕字幕，不超过36字"
    }
  ],
  "description": "发布简介80-120字，含#话题",
  "goal": "本片数据目标",
  "cta": "结尾行动引导",
  "lessons_used": ["本次引用了哪些经验，可为空数组"]
}
4. segments 数量 5-8 段，每段 text 长度按上面范围，全片解说总时长控制在60-90秒。
5. 全部简体中文，口语化、像真人说话。
6. 如果 dna.topic 为“信息不足”，不得创作，返回 {"error":"insufficient_source_context"}。"""


def rewrite(dna: dict, experience_context: str = "", model: str | None = None) -> dict:
    model = model or settings.rewrite_model
    user = {
        "dna": dna,
        "experience_context": experience_context or "（暂无历史经验）",
    }
    return chat_json(WRITER_SYSTEM, json.dumps(user, ensure_ascii=False),
                     model=model, temperature=0.6)
