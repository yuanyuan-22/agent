import json

import pytest

from forge.graph import render_approved_job
from forge.job_flow import approve_job, edit_job
from forge.store import create_job, get_job, update_job


def test_approve_job_requires_asset_pack(db):
    create_job("flow1", "source", "")
    with pytest.raises(RuntimeError):
        approve_job("flow1")

    update_job("flow1", asset_pack_path="asset_pack.json", status="awaiting_review")
    approve_job("flow1")
    assert get_job("flow1")["review_status"] == "approved"


def test_render_requires_approved_job(db):
    create_job("flow2", "source", "")
    with pytest.raises(RuntimeError):
        render_approved_job("flow2")


def test_edit_job_runs_review_and_rewrites_pack(db, tmp_path, monkeypatch):
    create_job("flow3", "source", "")
    update_job("flow3", run_dir=str(tmp_path), status="awaiting_review")
    (tmp_path / "source_video.json").write_text("{}", encoding="utf-8")
    (tmp_path / "dna.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ideas.json").write_text("[]", encoding="utf-8")
    (tmp_path / "script.json").write_text("{}", encoding="utf-8")
    (tmp_path / "storyboard.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "forge.job_flow.review_node",
        lambda state: {
            "review": {"pass": True, "score": 8, "topic_consistency": 8, "fact_support": 8},
            "decision": "pack_assets",
        },
    )
    monkeypatch.setattr(
        "forge.job_flow.pack_assets_node",
        lambda state: {"asset_pack": {"job_id": state["job_id"]}},
    )

    edit_job(
        "flow3",
        script={"title": "编辑标题", "segments": []},
        storyboard={"scenes": []},
    )

    saved = json.loads((tmp_path / "script.json").read_text(encoding="utf-8"))
    assert saved["title"] == "编辑标题"
