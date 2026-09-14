import math

from forge.experience import context_text, _cosine


def test_cosine_same():
    v = [1.0, 2.0, 3.0]
    assert abs(_cosine(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal():
    assert abs(_cosine([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_cosine_empty():
    assert _cosine([], [1.0]) == 0.0
    assert _cosine([1.0], []) == 0.0


def test_context_text_format():
    exps = [{"topic": "盐分", "title": "动物补盐", "insights": "标题要更抓眼",
             "metrics": {"view": 100, "like": 5}, "_score": 0.9}]
    text = context_text(exps)
    assert "历史经验库" in text
    assert "动物补盐" in text
    assert "100" in text


def test_context_text_empty():
    assert context_text([]) == ""
