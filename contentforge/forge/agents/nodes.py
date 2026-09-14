from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from forge.analyst import analyze
from forge.asset_pack import build_asset_pack, write_asset_pack
from forge.assets import AssetManager
from forge.config import settings
from forge.content_plan import CharacterBible
from forge.director import build_storyboard
from forge.generation.character import CharacterManager
from forge.generation.manager import GenerationManager
from forge.ideation import generate_ideas, select_best
from forge.media import render
from forge.pipeline import write_publish_pack
from forge.reviewer import review
from forge.source_service import SourceContentMissing, fetch_source_video
from forge.store import add_event, update_job
from forge.writer import rewrite


def _experience_context(dna: dict) -> str:
    try:
        from forge.experience import context_text, search

        query = " ".join(str(x) for x in (dna.get("topic", ""), dna.get("hook", "")))
        hits = search(query, top_k=3)
        return context_text(hits) if hits else ""
    except Exception:
        return ""


class JobState(TypedDict, total=False):
    job_id: str
    source: str
    channel: str
    target_platforms: list[str]
    manual: dict
    visual_style: str
    generation_mode: str
    character_id: str
    insight: dict
    ideas: list[dict]
    selected_idea: dict
    storyboard: dict
    run_dir: str
    style: str
    video: dict
    dna: dict
    script: dict
    feedback: str
    rewrite_count: int
    decision: str
    manual_review: bool
    asset_pack: dict
    media: dict
    error: str


MAX_REWRITES = 2


def _emit(job_id: str, kind: str, message: str = "", payload: dict | None = None) -> None:
    add_event(job_id, kind, message, payload)


def _rd(state: dict) -> Path:
    path = Path(state["run_dir"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetch_node(state: JobState) -> dict:
    job_id = state["job_id"]
    _emit(job_id, "start", "任务开始")
    run_dir = _rd(state)
    source = state["source"]
    channel = state.get("channel") or "auto"
    update_job(job_id, status="fetching", source=source)
    _emit(job_id, "step", f"抓取来源 {channel}: {source}")
    try:
        video = fetch_source_video(
            channel,
            source,
            on_status=lambda msg: add_event(job_id, "step", msg),
            manual=state.get("manual") or None,
        )
    except SourceContentMissing as exc:
        update_job(job_id, status="manual_required", error=str(exc)[:500])
        _emit(job_id, "manual_required", str(exc))
        raise
    with open(run_dir / "source_video.json", "w", encoding="utf-8") as f:
        json.dump(video, f, ensure_ascii=False, indent=2)
    mode = video.get("transcript_mode", "none")
    _emit(job_id, "step", f"文案来源: {mode}，转录字数 {len(video['transcript_text'])}",
          {"source_id": video.get("source_id"), "title": video.get("title"), "mode": mode,
           "transcript_len": len(video["transcript_text"])})
    update_job(job_id, title=(video.get("title") or "")[:80],
               channel=video.get("platform", channel))
    return {"video": video}


def analyze_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    update_job(job_id, status="planning")
    _emit(job_id, "step", "AnalystAgent 拆解爆款DNA")
    dna = analyze(state["video"])
    with open(run_dir / "dna.json", "w", encoding="utf-8") as f:
        json.dump(dna, f, ensure_ascii=False, indent=2)
    _emit(job_id, "step", "DNA 拆解完成", {"topic": dna.get("topic", ""),
                                          "hook": dna.get("hook", "")})
    return {"dna": dna, "insight": dna}


def ideate_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    _emit(job_id, "step", "IdeationAgent 生成并选择原创角度")
    ideas = generate_ideas(state.get("insight") or state.get("dna") or {})
    selected = select_best(ideas)
    with open(run_dir / "ideas.json", "w", encoding="utf-8") as f:
        json.dump(ideas, f, ensure_ascii=False, indent=2)
    with open(run_dir / "selected_idea.json", "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)
    _emit(job_id, "step", f"选题确定: {selected.get('title')}",
          {"angle": selected.get("angle"), "score": selected.get("total_score")})
    return {"ideas": ideas, "selected_idea": selected}


def write_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    retry = int(state.get("rewrite_count", 0))
    _emit(job_id, "step", f"WriterAgent 改写脚本 (第{retry + 1}稿)")
    dna = state["dna"]
    selected = state.get("selected_idea") or {}
    feedback = state.get("feedback", "")
    exp_text = _experience_context(dna)
    ctx = json.dumps({
        "dna_topic": dna.get("topic", ""),
        "selected_idea": selected,
    }, ensure_ascii=False)
    if exp_text:
        ctx += "\n\n" + exp_text
    if feedback:
        ctx += "\n审稿意见，请针对性修改:\n" + feedback
    if state.get("style"):
        ctx += f"\n语言风格要求: {state['style']}"
    script = rewrite(dna, experience_context=ctx)
    with open(run_dir / "script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    _emit(job_id, "step", "脚本完成", {"title": script.get("title", "")})
    return {"script": script}


def director_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    _emit(job_id, "step", "DirectorAgent 生成动画分镜")
    character = CharacterBible(character_id=state.get("character_id") or "host_default")
    storyboard = build_storyboard(
        state["script"],
        state.get("insight") or state.get("dna") or {},
        visual_style=state.get("visual_style") or "tech_infographic",
        generation_mode=state.get("generation_mode") or "balanced",
        character=character,
    )
    with open(run_dir / "storyboard.json", "w", encoding="utf-8") as f:
        json.dump(storyboard, f, ensure_ascii=False, indent=2)
    video_scenes = sum(1 for scene in storyboard.get("scenes") or []
                       if scene.get("asset_policy") == "generate_video")
    _emit(job_id, "step", f"分镜完成: {len(storyboard.get('scenes') or [])} 镜，"
                          f"{video_scenes} 个图生视频镜头")
    return {"storyboard": storyboard}


def review_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    retry = int(state.get("rewrite_count", 0))
    _emit(job_id, "step", "ReviewerAgent 审稿")
    verdict = review(state["dna"], state["script"])
    with open(run_dir / "review.json", "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)

    passed = bool(verdict.get("pass"))
    _emit(job_id, "review", f"审稿评分 {verdict.get('score')} → {'通过' if passed else '打回'}",
          {"score": verdict.get("score"), "pass": passed,
           "issues": verdict.get("issues", []), "hard": verdict.get("hard")})

    if passed:
        update_job(job_id, status="reviewed")
        return {"decision": "pack_assets", "rewrite_count": retry, "review": verdict}
    if retry < MAX_REWRITES:
        feedback = "；".join(verdict.get("issues", [])) + ("。修改建议：" + "；".join(verdict.get("suggestions", [])) if verdict.get("suggestions") else "")
        return {"decision": "writer", "rewrite_count": retry + 1, "review": verdict,
                "feedback": feedback or "请提升原创性与结构完整性"}
    update_job(job_id, manual_review=True)
    return {"decision": "pack_assets", "rewrite_count": retry, "manual_review": True,
            "review": verdict, "feedback": state.get("feedback", "")}


def pack_assets_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    _emit(job_id, "step", "生成内容资产包")
    pack = build_asset_pack(
        job_id=job_id,
        video=state.get("video") or {},
        dna=state.get("dna") or {},
        ideas=state.get("ideas") or [],
        selected_idea=state.get("selected_idea") or {},
        script=state.get("script") or {},
        storyboard=state.get("storyboard") or {},
        review=state.get("review") or {},
    )
    paths = write_asset_pack(pack, run_dir)
    result = {
        "source": state.get("video", {}).get("source_id") or state.get("video", {}).get("bvid"),
        "channel": state.get("video", {}).get("platform") or state.get("channel"),
        "source_title": state.get("video", {}).get("title"),
        "script_title": state.get("script", {}).get("title"),
        "transcript_mode": state.get("video", {}).get("transcript_mode"),
        "review": state.get("review") or None,
        "manual_review": bool(state.get("manual_review", False)),
        "asset_pack": paths,
        "run_dir": str(run_dir),
    }
    update_job(
        job_id,
        status="awaiting_review",
        review_status="pending",
        asset_pack_path=paths["json"],
        run_dir=str(run_dir),
        result=result,
    )
    _emit(
        job_id,
        "awaiting_review",
        "内容资产包已生成，等待人工审核",
        {"asset_pack": paths["markdown"], "review_score": (state.get("review") or {}).get("score")},
    )
    return {"asset_pack": pack}


def producer_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    update_job(job_id, status="rendering")
    _emit(job_id, "step", "ProducerAgent 配音+出片(逐段CosyVoice)")
    script = dict(state["script"])
    storyboard = state.get("storyboard") or {}
    generation = GenerationManager()
    character_bible = CharacterBible(**(storyboard.get("character") or {}))
    character_bible = CharacterManager(generation).ensure(character_bible, run_dir)
    if storyboard:
        storyboard = dict(storyboard)
        storyboard["character"] = character_bible.to_dict()
    scenes = storyboard.get("scenes") or []
    if scenes:
        merged_segments = []
        for index, segment in enumerate(script.get("segments") or []):
            scene = scenes[index] if index < len(scenes) else {}
            merged_segments.append({
                **segment,
                **scene,
                "text": segment.get("text") or scene.get("narration") or "",
                "caption": segment.get("caption") or scene.get("caption") or "",
                "visual_style": storyboard.get("visual_style"),
                "style_prompt": storyboard.get("style_prompt"),
                "character": storyboard.get("character"),
            })
        script["segments"] = merged_segments
    media = render(
        script,
        run_dir / "media",
        size=(settings.video_width, settings.video_height),
        bg=settings.video_bg,
        accent=settings.video_accent,
        fps=settings.video_fps,
        asset_manager=AssetManager(generation_manager=generation),
    )
    _emit(job_id, "step", f"成片完成 {media['duration_seconds']}s",
          {"video": media["video"], "duration": media["duration_seconds"]})
    return {"media": media}


def pack_node(state: JobState) -> dict:
    job_id = state["job_id"]
    run_dir = _rd(state)
    _emit(job_id, "step", "生成发布包(标题/标签/简介/封面)")
    write_publish_pack(state["script"], state["media"]["video"],
                       state["media"]["cover"], state["media"]["duration_seconds"], run_dir,
                       target_platforms=state.get("target_platforms") or ["bilibili"])
    result = {
        "source": state.get("video", {}).get("source_id") or state.get("video", {}).get("bvid"),
        "channel": state.get("video", {}).get("platform") or state.get("channel"),
        "source_title": state.get("video", {}).get("title"),
        "script_title": state.get("script", {}).get("title"),
        "transcript_mode": state.get("video", {}).get("transcript_mode"),
        "review": state.get("review") or None,
        "manual_review": bool(state.get("manual_review", False)),
        "media": state["media"],
        "run_dir": str(run_dir),
    }
    update_job(job_id, status="done", run_dir=str(run_dir), result=json.dumps(result, ensure_ascii=False))
    _emit(job_id, "done", "任务完成", {"manual_review": result["manual_review"]})
    return {}
