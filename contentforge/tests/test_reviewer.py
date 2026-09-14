from forge.reviewer import review, rule_check


def _script(seg_texts, title="测试标题", cover="封面字"):
    return {
        "title": title,
        "cover_text": cover,
        "tags": ["a", "b"],
        "segments": [{"heading": "", "text": t} for t in seg_texts],
        "description": "简介",
    }


def test_valid_passes():
    texts = ["这是一段" * 20] * 5
    assert rule_check(_script(texts)) == []


def test_missing_title():
    s = _script(["一段" * 40] * 5)
    s["title"] = ""
    assert "缺少标题" in rule_check(s)


def test_title_too_long():
    s = _script(["一段" * 40] * 5)
    s["title"] = "很" * 30
    assert any("标题过长" in p for p in rule_check(s))


def test_missing_cover():
    s = _script(["一段" * 40] * 5)
    s["cover_text"] = ""
    assert any("cover_text" in p or "封面" in p for p in rule_check(s))


def test_wrong_segment_count():
    s = _script(["一段" * 40] * 2)
    assert any("segments" in p for p in rule_check(s))


def test_segment_too_short_and_long():
    s = _script(["太短", "很长" * 100] + ["一段" * 40] * 3)
    problems = rule_check(s)
    assert any("过短" in p for p in problems)
    assert any("过长" in p for p in problems)


def test_forbidden_word():
    s = _script(["一段" * 40] * 5)
    s["description"] = "点击下方链接购买"
    assert any("违禁词" in p for p in rule_check(s))


def test_empty_segment():
    s = _script(["一段" * 40, ""] + ["一段" * 40] * 3)
    assert any("为空" in p for p in rule_check(s))


def test_review_hard_rejects_unsupported_facts(monkeypatch):
    monkeypatch.setattr(
        "forge.reviewer.chat_json",
        lambda *args, **kwargs: {
            "score": 9,
            "topic_consistency": 9,
            "fact_support": 2,
            "pass": True,
            "hard": False,
            "issues": [],
            "suggestions": [],
        },
    )
    script = _script(["这是一段" * 20] * 5)
    result = review({"topic": "桂林旅行", "facts": []}, script)
    assert result["pass"] is False
    assert result["hard"] is True
    assert any("缺少原文支撑" in item for item in result["issues"])
