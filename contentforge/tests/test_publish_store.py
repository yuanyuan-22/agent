import json

import pytest

from forge.loop import import_metrics
from forge.publish import mark_platform_published, prepare_publish_package
from forge.store import create_job, get_job, mark_published, record_metric, update_job


def test_multi_platform_publish_record(db):
    create_job("pub1", "https://v.douyin.com/abc", "", channel="douyin",
               target_platforms=["douyin", "xiaohongshu"])
    assert mark_published("pub1", "note-123", platform="xiaohongshu",
                          url="https://www.xiaohongshu.com/explore/note-123")
    job = get_job("pub1")
    assert job["channel"] == "douyin"
    assert "xiaohongshu" in job["publish_records"]
    assert job["publish_records"]["xiaohongshu"]["external_id"] == "note-123"


def test_metric_platform(db):
    create_job("pub2", "source", "")
    row = record_metric("pub2", {"view": 10, "like": 2}, platform="douyin")
    assert row["platform"] == "douyin"
    assert row["view"] == 10


def test_prepare_publish_package(db, tmp_path):
    create_job("pub3", "source", "", channel="douyin",
               target_platforms=["douyin", "xiaohongshu"])
    (tmp_path / "script.json").write_text(json.dumps({
        "title": "发布标题",
        "description": "发布简介",
        "tags": ["AI", "测试"],
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "publish_pack.json").write_text(json.dumps({
        "video": "final.mp4",
        "cover": "cover.png",
    }, ensure_ascii=False), encoding="utf-8")
    update_job("pub3", run_dir=str(tmp_path), status="done",
               result={"media": {"video": "final.mp4", "cover": "cover.png"}})
    package = prepare_publish_package("pub3")
    assert set(package["platforms"].keys()) == {"douyin", "xiaohongshu"}
    assert (tmp_path / "publish" / "douyin.json").exists()
    assert (tmp_path / "publish" / "xiaohongshu.txt").exists()


def test_bilibili_publish_accepts_full_url(db):
    create_job("pub4", "source", "")
    job = mark_platform_published(
        "pub4",
        "bilibili",
        "https://www.bilibili.com/video/BV1VxYM6PEew/?share_source=copy_web",
    )
    assert job["publish_records"]["bilibili"]["external_id"] == "BV1VxYM6PEew"


def test_import_metrics_requires_existing_job(db):
    with pytest.raises(ValueError):
        import_metrics("missing", {"view": 1}, platform="douyin")
