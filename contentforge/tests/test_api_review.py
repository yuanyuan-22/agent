from fastapi.testclient import TestClient

from forge.server import app as server_app


def test_render_endpoint_requires_approval(monkeypatch):
    monkeypatch.setattr(
        server_app,
        "get_job",
        lambda _job_id: {"id": "j1", "review_status": "pending"},
    )
    client = TestClient(server_app.app)
    response = client.post("/api/jobs/j1/render")
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "审核通过" in response.json()["error"]


def test_review_endpoint_rejects_unknown_action(monkeypatch):
    monkeypatch.setattr(
        server_app,
        "get_job",
        lambda _job_id: {"id": "j1", "review_status": "pending"},
    )
    client = TestClient(server_app.app)
    response = client.post("/api/jobs/j1/review", json={"action": "unknown"})
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_approved_job_can_start_render(monkeypatch):
    calls = {}

    class FakeThread:
        def __init__(self, target, args, daemon):
            calls["target"] = target
            calls["args"] = args
            calls["daemon"] = daemon

        def start(self):
            calls["started"] = True

    monkeypatch.setattr(
        server_app,
        "get_job",
        lambda job_id: {
            "id": job_id,
            "status": "approved",
            "review_status": "approved",
        },
    )
    monkeypatch.setattr(
        server_app,
        "update_job",
        lambda job_id, **fields: calls.setdefault("update", (job_id, fields)),
    )
    monkeypatch.setattr(server_app, "add_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(server_app.threading, "Thread", FakeThread)

    client = TestClient(server_app.app)
    response = client.post("/api/jobs/j1/render")

    assert response.json()["ok"] is True
    assert calls["started"] is True
    assert calls["update"][1]["status"] == "rendering"
