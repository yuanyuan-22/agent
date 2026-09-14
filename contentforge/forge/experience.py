from __future__ import annotations

import json

import numpy as np

from forge.llm import embed
from forge.store import load_embeddings, upsert_experience


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    if va.size == 0 or vb.size == 0:
        return 0.0
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _compose(topic: str, title: str, insights: str) -> str:
    return "\n".join(x for x in (topic, title, insights) if x).strip()


def search(query: str, top_k: int = 3) -> list[dict]:
    rows = load_embeddings()
    if not rows:
        return []
    qv = embed([query])[0]
    scored = []
    for r in rows:
        r["_score"] = _cosine(qv, r["embedding"])
        scored.append(r)
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:top_k]


def add_experience(source_job_id: str, topic: str, title: str, insights: str,
                   metrics: dict, score: float) -> int:
    text = _compose(topic, title, insights)
    vector = embed([text])[0]
    return upsert_experience(source_job_id, topic, title, insights,
                             metrics, vector, score)


def context_text(exps: list[dict]) -> str:
    if not exps:
        return ""
    lines = ["=== 历史经验库（数据回流沉淀，写作时参考，不要照抄）==="]
    for i, e in enumerate(exps, 1):
        m = e.get("metrics") or {}
        lines.append(
            f"[经验{i}] 主题:{e.get('topic','')} | 标题:{e.get('title','')} | "
            f"播放:{m.get('view',0)} 赞:{m.get('like',0)}\n{e.get('insights','')}")
    return "\n".join(lines)
