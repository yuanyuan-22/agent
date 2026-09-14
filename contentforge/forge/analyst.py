from __future__ import annotations

import json

from forge.llm import chat_json

ANALYST_SYSTEM = """你是资深的短视频内容洞察分析师。给你一个热门视频的元信息（平台/标题/作者/数据/简介/字幕），请提炼可复用的「内容洞察」。
规则：
1. 只输出一个 JSON 对象，不要输出任何其它文字。
2. schema 如下：
{
  "topic": "一句话主题",
  "audience": "目标人群",
  "emotion": "主要情绪和情绪变化",
  "hook_formula": "前3秒钩子的结构公式",
  "structure": ["内容结构要点，最多6条，每条不超过25字"],
  "key_points": ["可复用的信息点/观点，最多6条"],
  "facts": [{"claim": "原文明确支持的事实", "evidence": "对应原文中的短句或字段"}],
  "visual_motifs": ["适合动画表达的视觉意象，最多6条"],
  "comments_needs": ["评论/用户可能最关心的需求，最多5条"],
  "why_viral": "为什么这条内容能传播，短而具体",
  "platform_signals": {"platform": "平台名", "metrics": {"view": 0, "like": 0}},
  "duration_seconds": 数字
}
3. 必须保持原内容的主题、人物、场景、平台语境和核心信息，不得换成无关领域。
4. 字幕缺失时只能基于标题、简介、分享文案和现有数据做有限归纳，不得补写原标题中不存在的具体事实或案例。
5. 如果输入信息不足，topic 写“信息不足”，并在 why_viral 中说明缺少哪些信息，禁止猜测成另一个故事。
6. facts 只能来自输入中的标题、简介、分享文案或字幕，不能根据常识补写案例、数字或结论。
7. 全部用简体中文。"""


def analyze(video: dict) -> dict:
    payload = {
        "bvid": video.get("bvid"),
        "platform": video.get("platform"),
        "source_id": video.get("source_id"),
        "source_url": video.get("source_url"),
        "title": video.get("title"),
        "tname": video.get("tname"),
        "up": video.get("owner"),
        "stat": video.get("stat"),
        "transcript_mode": video.get("transcript_mode"),
        "desc": (video.get("desc") or "")[:500],
        "subtitle": (video.get("transcript_text") or video.get("subtitle_text") or "")[:4000],
    }
    dna = chat_json(ANALYST_SYSTEM, json.dumps(payload, ensure_ascii=False), temperature=0.2)
    dna.setdefault("hook_style", dna.get("hook_formula", ""))
    dna.setdefault("hook", dna.get("hook_formula", ""))
    dna.setdefault("tone", video.get("style") or "")
    dna["source"] = {
        "bvid": video.get("bvid"),
        "platform": video.get("platform"),
        "source_id": video.get("source_id"),
        "source_url": video.get("source_url"),
        "title": video.get("title"),
        "up": video.get("owner"),
    }
    return dna
