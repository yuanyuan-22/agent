from forge.agents import nodes
from forge.graph import build_graph


def test_default_graph_stops_at_asset_pack():
    graph = build_graph()
    nodes = set(graph.get_graph().nodes)
    assert "pack_assets" in nodes
    assert "producer" not in nodes


def test_review_routes_to_pack_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(
        nodes,
        "review",
        lambda _dna, _script: {
            "pass": True,
            "score": 9,
            "issues": [],
            "suggestions": [],
            "hard": False,
        },
    )
    monkeypatch.setattr(nodes, "_emit", lambda *args, **kwargs: None)
    monkeypatch.setattr(nodes, "update_job", lambda *args, **kwargs: None)
    result = nodes.review_node(
        {
            "job_id": "route1",
            "run_dir": str(tmp_path),
            "dna": {"topic": "RAG"},
            "script": {"segments": []},
        }
    )
    assert result["decision"] == "pack_assets"
