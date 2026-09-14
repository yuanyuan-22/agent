import forge.director as director


def test_storyboard_fallback_without_llm(monkeypatch):
    monkeypatch.setattr(director, "chat_json", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no llm")))
    script = {
        "title": "测试",
        "segments": [{"heading": f"段{i}", "text": "内容" * 20} for i in range(5)],
    }
    board = director.build_storyboard(script, {"topic": "测试"}, generation_mode="balanced")
    assert len(board["scenes"]) == 5
    assert board["scenes"][0]["purpose"] == "hook"
    assert board["scenes"][-1]["purpose"] == "cta"
    assert len(board["character"]["character_id"]) > 0
