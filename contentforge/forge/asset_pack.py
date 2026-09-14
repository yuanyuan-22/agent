from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _fact_rows(dna: Dict[str, Any]) -> List[Dict[str, str]]:
    rows = dna.get("facts") or []
    facts: List[Dict[str, str]] = []
    for row in rows:
        if isinstance(row, dict):
            claim = str(row.get("claim") or row.get("text") or "").strip()
            evidence = str(row.get("evidence") or row.get("source") or "").strip()
        else:
            claim = str(row or "").strip()
            evidence = ""
        if claim:
            facts.append({"claim": claim, "evidence": evidence})
    if facts:
        return facts
    return [
        {"claim": str(item).strip(), "evidence": ""}
        for item in (dna.get("key_points") or [])
        if str(item).strip()
    ]


def build_asset_pack(
    *,
    job_id: str,
    video: Dict[str, Any],
    dna: Dict[str, Any],
    ideas: List[Dict[str, Any]],
    selected_idea: Dict[str, Any],
    script: Dict[str, Any],
    storyboard: Dict[str, Any],
    review: Dict[str, Any],
) -> Dict[str, Any]:
    transcript = str(video.get("transcript_text") or video.get("subtitle_text") or "")
    return {
        "job_id": job_id,
        "source": {
            "platform": video.get("platform") or "",
            "source_id": video.get("source_id") or video.get("bvid") or "",
            "source_url": video.get("source_url") or "",
            "title": video.get("title") or "",
            "author": video.get("owner") or "",
            "transcript_mode": video.get("transcript_mode") or "none",
            "transcript_excerpt": transcript[:800],
        },
        "facts": _fact_rows(dna),
        "ideas": ideas,
        "selected_idea": selected_idea,
        "selected_script": script,
        "storyboard": storyboard,
        "publish_copy": {
            "title": script.get("title") or "",
            "cover_text": script.get("cover_text") or "",
            "description": script.get("description") or "",
            "tags": script.get("tags") or [],
            "cta": script.get("cta") or "",
        },
        "review": review,
        "artifacts": {},
    }


def write_asset_pack(pack: Dict[str, Any], run_dir: Path) -> Dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "asset_pack.json"
    md_path = run_dir / "content_assets.md"
    pack = dict(pack)
    pack["artifacts"] = {
        **(pack.get("artifacts") or {}),
        "asset_pack_json": str(json_path),
        "content_assets_md": str(md_path),
        "script": str(run_dir / "script.json"),
        "storyboard": str(run_dir / "storyboard.json"),
        "review": str(run_dir / "review.json"),
    }
    json_path.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(render_asset_markdown(pack), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_asset_markdown(pack: Dict[str, Any]) -> str:
    source = pack.get("source") or {}
    script = pack.get("selected_script") or {}
    review = pack.get("review") or {}
    lines = [
        f"# {script.get('title') or source.get('title') or '内容资产包'}",
        "",
        "## 来源",
        f"- 平台：{source.get('platform') or '-'}",
        f"- 标题：{source.get('title') or '-'}",
        f"- 作者：{source.get('author') or '-'}",
        f"- 原文模式：{source.get('transcript_mode') or '-'}",
        f"- 链接：{source.get('source_url') or '-'}",
        "",
        "## 事实摘要",
    ]
    facts = pack.get("facts") or []
    lines.extend(
        [f"- {item.get('claim')}" for item in facts if item.get("claim")]
        or ["- 暂无可验证事实点"]
    )
    lines.extend(["", "## 选题角度"])
    for index, idea in enumerate(pack.get("ideas") or [], start=1):
        lines.append(
            f"{index}. {idea.get('title') or '-'}：{idea.get('hook') or ''}"
        )
    lines.extend(
        [
            "",
            "## 主脚本",
            f"**标题：** {script.get('title') or '-'}",
            f"**封面：** {script.get('cover_text') or '-'}",
            "",
        ]
    )
    for index, segment in enumerate(script.get("segments") or [], start=1):
        heading = segment.get("heading") or f"第 {index} 段"
        lines.extend(
            [
                f"### {heading}",
                segment.get("text") or "",
                f"字幕：{segment.get('caption') or ''}",
                "",
            ]
        )
    lines.extend(
        [
            "## 发布信息",
            f"- 简介：{script.get('description') or '-'}",
            f"- 标签：{' '.join(script.get('tags') or []) or '-'}",
            f"- CTA：{script.get('cta') or '-'}",
            "",
            "## 审核",
            f"- 结果：{'通过' if review.get('pass') else '待修改'}",
            f"- 分数：{review.get('score', '-')}",
            f"- 主题一致性：{review.get('topic_consistency', '-')}",
            f"- 事实支撑：{review.get('fact_support', '-')}",
        ]
    )
    issues = review.get("issues") or []
    if issues:
        lines.append("- 问题：")
        lines.extend(f"  - {issue}" for issue in issues)
    lines.append("")
    return "\n".join(lines)


def load_asset_pack(path: str | Path) -> Dict[str, Any] | None:
    value = Path(path)
    if not value.exists():
        return None
    try:
        return json.loads(value.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
