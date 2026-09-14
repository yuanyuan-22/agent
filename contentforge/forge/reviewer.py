from __future__ import annotations

import json

from forge.llm import chat_json

FORBIDDEN_WORDS = [
    "最厉害", "第一品牌", "绝对", "根治", "包治百病", "点击下方链接购买",
    "加微信", "进群", "免费领取", "不买后悔",
]

REVIEWER_SYSTEM = """你是短视频平台的主编审稿人，负责判断一条脚本是否可以发布。
依据：参考视频的「爆款DNA」与待审「脚本」。
打分维度：
1. 原创性(0-10)：脚本文字不得照抄参考视频的字幕/简介，必须有新表达。
2. 爆点(0-10)：标题有钩子，开头抓人，结构完整（开头钩子→主体→结尾引导）。
3. 合规(0-10)：无违禁词、无夸大医疗/投资承诺、无营销导流话术。
4. 节奏(0-10)：segments 数量4-6，每段60-130字，口语化适合配音。
5. 主题一致性(0-10)：脚本主题、人物、场景和核心信息必须与参考内容的 DNA 一致；换题或编造新故事直接 hard=true。
6. 事实支撑(0-10)：脚本中的关键事实必须能在 DNA 的 facts、key_points、标题或原文摘要中找到依据；无依据的具体数字、案例和结论直接 hard=true。
只输出 JSON：
{"score": 总分0-10, "topic_consistency": 0-10, "fact_support": 0-10, "pass": true/false, "issues": ["具体问题，最多4条"], "suggestions": ["可执行修改建议，最多3条"], "hard": true/false}
hard=true 表示原创/合规存在硬伤，必须打回。"""


def rule_check(script: dict) -> list[str]:
    problems: list[str] = []
    segments = script.get("segments") or []
    title = (script.get("title") or "").strip()
    if not title:
        problems.append("缺少标题")
    elif len(title) > 26:
        problems.append(f"标题过长({len(title)}字，建议≤22)")
    if not script.get("cover_text"):
        problems.append("缺少封面大字 cover_text")
    if not (4 <= len(segments) <= 6):
        problems.append(f"segments 数量为{len(segments)}，建议4-6")
    for i, seg in enumerate(segments, 1):
        ln = len((seg.get("text") or "").strip())
        if not seg.get("text"):
            problems.append(f"第{i}段为空")
        elif ln < 50:
            problems.append(f"第{i}段过短({ln}字)")
        elif ln > 150:
            problems.append(f"第{i}段过长({ln}字)")
    text_all = json.dumps(script, ensure_ascii=False)
    for w in FORBIDDEN_WORDS:
        if w in text_all:
            problems.append(f"命中疑似违禁词：{w}")
    return problems


def review(dna: dict, script: dict, model: str | None = None) -> dict:
    rule_problems = rule_check(script)
    user = {
        "dna": dna,
        "script": script,
        "hard_rule_notes": rule_problems or [],
    }
    try:
        judge = chat_json(REVIEWER_SYSTEM, json.dumps(user, ensure_ascii=False),
                          model=model, temperature=0.2)
    except Exception as e:
        judge = {"score": 5, "pass": True, "issues": [], "suggestions": [],
                 "hard": False, "judge_error": str(e)}

    hard = bool(judge.get("hard"))
    llm_pass = bool(judge.get("pass"))
    score = float(judge.get("score", 0))
    topic_consistency = float(judge.get("topic_consistency", 10))
    fact_support = float(judge.get("fact_support", 10))
    judge_error = judge.get("judge_error")

    if topic_consistency < 7:
        hard = True
        issues_topic = "脚本主题与原内容不一致"
    else:
        issues_topic = ""
    if fact_support < 7:
        hard = True
        issues_fact = "脚本存在缺少原文支撑的事实或推断"
    else:
        issues_fact = ""

    passed = (
        (not hard)
        and llm_pass
        and (score >= 6)
        and (topic_consistency >= 7)
        and (fact_support >= 7)
        and (not rule_problems)
    )
    issues = list(rule_problems)
    issues += [str(x) for x in judge.get("issues", [])]
    if issues_topic:
        issues.insert(0, issues_topic)
    if issues_fact:
        issues.insert(0, issues_fact)
    if judge_error:
        issues.append(f"LLM 审稿不可用，已按放行处理: {judge_error}")
    return {
        "score": round(score, 1),
        "topic_consistency": round(topic_consistency, 1),
        "fact_support": round(fact_support, 1),
        "pass": passed,
        "hard": hard,
        "issues": issues[:6],
        "suggestions": judge.get("suggestions", []),
        "rule_problems": rule_problems,
    }
