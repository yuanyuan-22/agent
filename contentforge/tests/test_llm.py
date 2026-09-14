from forge.llm import _friendly_error, extract_json


def test_balance_error_has_actionable_message():
    error = RuntimeError("Error code: 402 - {'code': 30001, 'message': 'balance is insufficient'}")
    friendly = _friendly_error(error)
    assert "余额不足" in str(friendly)
    assert "DEEPSEEK_API_KEY" in str(friendly)


def test_clean_json():
    assert extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_code_fence():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_trailing_prose():
    text = '好的，这是结果：{"a": [1, 2, 3]} 希望有帮助。'
    assert extract_json(text) == {"a": [1, 2, 3]}


def test_multiline_utf8():
    text = '{\n  "标题": "动物从不吃盐？",\n  "tags": ["冷知识", "科普"]\n}'
    out = extract_json(text)
    assert out["标题"] == "动物从不吃盐？"
    assert out["tags"] == ["冷知识", "科普"]


def test_nested_object():
    text = '{"m": {"view": 10, "like": 2}}'
    assert extract_json(text)["m"]["like"] == 2


def test_invalid_raises():
    try:
        extract_json("no json here")
        raise AssertionError("should raise")
    except ValueError:
        pass
