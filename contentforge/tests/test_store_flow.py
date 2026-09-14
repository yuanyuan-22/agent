from forge.store import (add_event, create_job, events_after, get_job, list_experiences,
                         list_metrics, mark_published, record_metric, update_job,
                         upsert_experience)


def test_job_crud(db):
    create_job("j1", "BV1TEST", "风格A")
    created = get_job("j1")
    assert created["review_status"] == "pending"
    assert created["asset_pack_path"] == ""
    update_job("j1", status="done", title="标题T")
    job = get_job("j1")
    assert job["status"] == "done"
    assert job["title"] == "标题T"
    assert get_job("missing") is None


def test_publish_flow(db):
    create_job("j2", "BV1TEST", "")
    assert mark_published("j2", "BV1MINE") is True
    job = get_job("j2")
    assert job["published"] is True
    assert job["own_bvid"] == "BV1MINE"
    assert job["status"] == "published"
    assert mark_published("nope", "BV1") is False


def test_metrics(db):
    create_job("j3", "BV1TEST", "")
    row = record_metric("j3", {"view": 100, "like": 3, "coin": 1, "share": 0,
                               "favorite": 2, "danmaku": 4, "reply": 1})
    assert row["view"] == 100
    rows = list_metrics("j3")
    assert len(rows) == 1
    assert rows[0]["like"] == 3


def test_experience_upsert(db):
    create_job("j4", "BV1TEST", "")
    id1 = upsert_experience("j4", "t", "标题", "insights", {"view": 1}, [1.0, 0.0], 9.0)
    id2 = upsert_experience("j4", "t", "标题2", "insights2", {"view": 2}, [0.0, 1.0], 8.0)
    assert id1 == id2
    rows = list_experiences()
    assert len(rows) == 1
    assert rows[0]["title"] == "标题2"
    assert rows[0]["metrics"]["view"] == 2


def test_events_after(db):
    create_job("j5", "BV1TEST", "")
    e1 = add_event("j5", "start", "开始")
    e2 = add_event("j5", "step", "抓取")
    all_ev = events_after("j5", 0)
    assert [e["kind"] for e in all_ev] == ["start", "step"]
    new_ev = events_after("j5", e1)
    assert len(new_ev) == 1 and new_ev[0]["kind"] == "step"
