from __future__ import annotations

import json

from forge.llm import chat_json

REPLIER_SYSTEM = """你是短视频账号的复盘运营负责人。给定一条已发布视频的「脚本主题/标题/创作说明」和它的「数据表现」，输出结构化复盘。
输出 JSON：
{
  "verdict": "一句话数据结论(播放/赞/互动是否达标)",
  "lessons": ["可复用的经验/教训，最多4条，写给下一次写作参考，要具体可执行"],
  "suggestions": ["下一步改进动作，最多3条"],
  "keep_topic": true或false(这个方向是否值得继续做)
}
要求：经验要落到"选题/标题/开头钩子/结构/结尾引导/发布时间"等可操作层面，不要空话。"""


def _load_run_files(run_dir: str) -> dict:
    from pathlib import Path

    base = Path(run_dir)
    data = {}
    for name in ("script.json", "dna.json"):
        p = base / name
        if p.exists():
            try:
                data[name] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data[name] = {}
    return data


def build_insights(job: dict, metric: dict | None = None) -> dict:
    run_dir = job.get("run_dir") or ""
    files = _load_run_files(run_dir)
    script = files.get("script.json") or {}
    dna = files.get("dna.json") or {}
    m = metric or {}
    payload = {
        "script": {
            "title": script.get("title", ""),
            "tags": script.get("tags", []),
            "description": (script.get("description") or "")[:200],
            "segments_count": len(script.get("segments") or []),
            "goal": script.get("goal", ""),
        },
        "dna_topic": dna.get("topic", ""),
        "dna_hook": dna.get("hook", ""),
        "metrics": {
            "view": m.get("view", 0), "like": m.get("like", 0),
            "coin": m.get("coin", 0), "share": m.get("share", 0),
            "favorite": m.get("favorite", 0), "reply": m.get("reply", 0),
        },
    }
    return chat_json(REPLIER_SYSTEM, json.dumps(payload, ensure_ascii=False),
                     temperature=0.3)
