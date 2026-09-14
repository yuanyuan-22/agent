"""离线审计 ContentForge 运行产物：Review 通过率、规则合规、失败原因等。

用法：
    python -m forge.evalkit                     # 扫描 runs/ 全部产物
    python -m forge.evalkit --jobs 0e3ec259f104 # 只看指定任务
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from forge.config import settings
from forge.reviewer import rule_check


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def audit_run(run_dir: Path) -> Dict[str, Any]:
    script = _read_json(run_dir / "script.json")
    review = _read_json(run_dir / "review.json")
    source = _read_json(run_dir / "source_video.json")
    result = _read_json(run_dir / "result.json")

    rule_problems: List[str] = []
    if script:
        try:
            rule_problems = rule_check(script)
        except Exception:
            rule_problems = ["script schema 解析失败"]

    review_pass = bool(review.get("pass"))
    review_score = review.get("score")
    segments = script.get("segments") or []
    lessons = script.get("lessons_used") or []

    return {
        "job_id": run_dir.name,
        "has_script": bool(script),
        "rule_pass": not rule_problems,
        "rule_problems": rule_problems[:6],
        "review_pass": review_pass if review else None,
        "review_score": review_score,
        "review_issues": (review.get("issues") or [])[:6],
        "manual_review": bool(review.get("hard") or result.get("manual_review")),
        "segment_count": len(segments),
        "segment_chars": [len(str(s.get("text", ""))) for s in segments],
        "lessons_used": len(lessons),
        "source": source.get("bvid") or "",
        "title": script.get("title") or "",
    }


def scan_runs(work_dir: Optional[Path] = None, job_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    root = work_dir or settings.work_dir
    rows: List[Dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in sorted(root.iterdir()):
        if not path.is_dir() or not (path / "script.json").exists():
            continue
        if job_ids and path.name not in job_ids:
            continue
        rows.append(audit_run(path))
    return rows


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"jobs": 0}

    rule_pass = sum(1 for row in rows if row.get("rule_pass"))
    reviewed = [row for row in rows if row.get("review_pass") is not None]
    review_pass = sum(1 for row in reviewed if row.get("review_pass"))
    manual = sum(1 for row in rows if row.get("manual_review"))
    seg_counts = [row["segment_count"] for row in rows if row.get("segment_count")]
    lesson_counts = [row["lessons_used"] for row in rows]
    char_lengths = [length for row in rows for length in row.get("segment_chars", [])]
    failures = Counter()
    for row in rows:
        for problem in row.get("rule_problems", []):
            failures[problem] += 1

    return {
        "jobs": len(rows),
        "rule_pass_rate": round(rule_pass / len(rows), 4),
        "reviewed": len(reviewed),
        "review_pass_rate": round(review_pass / max(1, len(reviewed)), 4),
        "manual_review_rate": round(manual / len(rows), 4),
        "median_segments": round(statistics.median(seg_counts), 1) if seg_counts else 0,
        "median_segment_chars": round(statistics.median(char_lengths), 1) if char_lengths else 0,
        "median_lessons_used": round(statistics.median(lesson_counts), 1) if lesson_counts else 0,
        "top_rule_failures": failures.most_common(8),
    }


def print_summary(summary: Dict[str, Any]) -> None:
    if summary.get("jobs") == 0:
        print("NO_RUNS")
        return
    print("=" * 64)
    print(f"jobs                {summary['jobs']}")
    print(f"rule_pass_rate      {summary['rule_pass_rate']:.2%}")
    print(f"review_pass_rate    {summary['review_pass_rate']:.2%} ({summary['reviewed']} reviewed)")
    print(f"manual_review_rate  {summary['manual_review_rate']:.2%}")
    print(f"median_segments     {summary['median_segments']}")
    print(f"median_segment_chars {summary['median_segment_chars']}")
    print(f"median_lessons_used {summary['median_lessons_used']}")
    print("-" * 64)
    for label, count in summary.get("top_rule_failures", []):
        print(f"failure {count:2d}  {label}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", nargs="*", default=None, help="只审计指定 job_id")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    rows = scan_runs(job_ids=args.jobs)
    summary = summarize(rows)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_summary(summary)


if __name__ == "__main__":
    main()
