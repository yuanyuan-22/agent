import json

from forge.evalkit import audit_run, scan_runs, summarize
from forge.reviewer import rule_check


def _write_run(root, job_id, script, review=None):
    d = root / job_id
    d.mkdir(parents=True)
    (d / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    if review is not None:
        (d / "review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")


def test_audit_valid_script(tmp_path):
    script = {
        "title": "标题",
        "cover_text": "封面",
        "segments": [{"text": "内容" * 40} for _ in range(5)],
        "description": "简介",
        "lessons_used": ["经验"],
    }
    _write_run(tmp_path, "abc", script, {"pass": True, "score": 8, "issues": []})
    row = audit_run(tmp_path / "abc")
    assert row["rule_pass"] is True
    assert row["review_pass"] is True
    assert row["segment_count"] == 5


def test_scan_summary(tmp_path):
    good = {
        "title": "标题",
        "cover_text": "封面",
        "segments": [{"text": "内容" * 40} for _ in range(5)],
        "description": "简介",
    }
    bad = dict(good)
    bad["description"] = "点击下方链接购买"
    _write_run(tmp_path, "good", good, {"pass": True, "score": 8, "issues": []})
    _write_run(tmp_path, "bad", bad, {"pass": False, "score": 4, "issues": ["违禁词"]})

    rows = scan_runs(work_dir=tmp_path)
    summary = summarize(rows)
    assert summary["jobs"] == 2
    assert summary["rule_pass_rate"] == 0.5
    assert summary["review_pass_rate"] == 0.5


def test_review_rule_used():
    script = {
        "title": "标题",
        "cover_text": "封面",
        "segments": [{"text": "内容" * 40} for _ in range(5)],
        "description": "免费领取",
    }
    assert any("违禁词" in p for p in rule_check(script))
