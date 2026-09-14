from __future__ import annotations

import json
from pathlib import Path

from forge.analyst import analyze
from forge.asset_pack import build_asset_pack, write_asset_pack
from forge.assets import AssetManager
from forge.content_plan import CharacterBible
from forge.director import build_storyboard
from forge.generation.character import CharacterManager
from forge.generation.manager import GenerationManager
from forge.ideation import generate_ideas, select_best
from forge.channels.bilibili import BiliClient, parse_bvid
from forge.config import settings
from forge.media import render
from forge.source_service import fetch_source_video
from forge.writer import rewrite
from forge.reviewer import review


def _dump(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_publish_pack(script: dict, video_path: str, cover_path: str,
                       duration_seconds: float, out_dir: Path,
                       target_platforms: list[str] | None = None) -> None:
    meta = {
        "title": script.get("title", ""),
        "tags": script.get("tags", []),
        "description": script.get("description", ""),
        "video": video_path,
        "cover": cover_path,
        "duration_seconds": duration_seconds,
        "target_platforms": target_platforms or ["bilibili"],
    }
    _dump(meta, out_dir / "publish_pack.json")
    lines = [
        "== 标题 ==",
        meta["title"],
        "",
        "== 标签 ==",
        " ".join(meta["tags"]),
        "",
        "== 简介 ==",
        meta["description"],
    ]
    (out_dir / "发布文案.txt").write_text("\n".join(lines), encoding="utf-8")


def run_vertical_slice(bvid: str, run_dir: Path, do_render: bool = False,
                       experience_context: str = "", language_style: str = "",
                       channel: str = "bilibili",
                       target_platforms: list[str] | None = None,
                       visual_style: str = "tech_infographic",
                       generation_mode: str = "balanced",
                       character_id: str = "host_default") -> dict:
    video = fetch_source_video(channel, bvid)

    run_dir.mkdir(parents=True, exist_ok=True)
    _dump(video, run_dir / "source_video.json")

    dna = analyze(video)
    _dump(dna, run_dir / "dna.json")
    ideas = generate_ideas(dna)
    selected = select_best(ideas)
    _dump(ideas, run_dir / "ideas.json")

    ctx = experience_context
    if language_style:
        style_hint = f"\n整体语言风格要求：{language_style}"
        ctx = (ctx + style_hint).strip()
    ctx = json.dumps({"dna_topic": dna.get("topic", ""), "selected_idea": selected},
                     ensure_ascii=False) + "\n\n" + ctx
    script = rewrite(dna, experience_context=ctx)
    _dump(script, run_dir / "script.json")
    generation = GenerationManager()
    character = CharacterManager(generation).ensure(
        CharacterBible(character_id=character_id), run_dir
    )
    storyboard = build_storyboard(
        script,
        dna,
        visual_style=visual_style,
        generation_mode=generation_mode,
        character=character,
    )
    _dump(storyboard, run_dir / "storyboard.json")
    verdict = review(dna, script)
    _dump(verdict, run_dir / "review.json")
    asset_pack = build_asset_pack(
        job_id=run_dir.name,
        video=video,
        dna=dna,
        ideas=ideas,
        selected_idea=selected,
        script=script,
        storyboard=storyboard,
        review=verdict,
    )
    asset_paths = write_asset_pack(asset_pack, run_dir)

    result = {
        "source": video.get("source_id") or video.get("bvid"),
        "channel": video.get("platform", channel),
        "source_title": video["title"],
        "dna_path": str(run_dir / "dna.json"),
        "script_path": str(run_dir / "script.json"),
        "script": script,
        "review": verdict,
        "asset_pack": asset_paths,
    }

    if do_render:
        merged_script = dict(script)
        merged_segments = []
        scenes = storyboard.get("scenes") or []
        for index, segment in enumerate(script.get("segments") or []):
            scene = scenes[index] if index < len(scenes) else {}
            merged_segments.append({
                **segment,
                **scene,
                "text": segment.get("text") or scene.get("narration") or "",
                "caption": segment.get("caption") or scene.get("caption") or "",
                "style_prompt": storyboard.get("style_prompt"),
                "character": storyboard.get("character"),
            })
        merged_script["segments"] = merged_segments
        media = render(
            merged_script,
            run_dir / "media",
            size=(settings.video_width, settings.video_height),
            bg=settings.video_bg,
            accent=settings.video_accent,
            fps=settings.video_fps,
            asset_manager=AssetManager(generation_manager=generation),
        )
        result["media"] = media
        write_publish_pack(script, media["video"], media["cover"],
                           media["duration_seconds"], run_dir,
                           target_platforms=target_platforms)
        result["publish_pack_path"] = str(run_dir / "publish_pack.json")
        result["txt_path"] = str(run_dir / "发布文案.txt")

    result["run_dir"] = str(run_dir)
    _dump(result, run_dir / "result.json")
    return result


def pick_trending_bvid(client: BiliClient, with_subtitle: bool = True) -> str:
    for item in client.trending(limit=10):
        bvid = item["bvid"]
        try:
            info = client.view(bvid)
        except Exception:
            continue
        cid = int(info.get("cid") or 0)
        if not cid:
            continue
        if with_subtitle and not client.subtitle_list(bvid, cid):
            continue
        return bvid
    return client.trending(limit=10)[0]["bvid"]


def main() -> None:
    import argparse
    import datetime

    parser = argparse.ArgumentParser(description="ContentForge 垂直切片：爆款→拆解→改写→出片")
    parser.add_argument("--bvid", help="B站 BVID 或完整链接")
    parser.add_argument("--source", help="任意平台分享链接；不填时兼容 --bvid")
    parser.add_argument("--channel", default="auto", help="bilibili/douyin/kuaishou/xiaohongshu")
    parser.add_argument("--targets", default="bilibili", help="逗号分隔的目标发布平台")
    parser.add_argument("--visual-style", default="tech_infographic",
                        choices=["tech_infographic", "anime", "realistic"])
    parser.add_argument("--generation-mode", default="balanced",
                        choices=["balanced", "low_cost", "high_quality"])
    parser.add_argument("--character-id", default="host_default")
    parser.add_argument("--auto", action="store_true", help="自动从热门榜挑一条")
    parser.add_argument("--render", action="store_true", help="审核链路之外的可选视频渲染")
    parser.add_argument("--no-render", action="store_true",
                        help="兼容旧命令；默认就是只生成内容资产包")
    parser.add_argument("--style", default="", help="可选：整体语言风格要求")
    args = parser.parse_args()

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = settings.work_dir / f"run_{ts}"

    if args.auto:
        client = BiliClient()
        try:
            bvid = pick_trending_bvid(client)
        finally:
            client.close()
        print(f"自动选中热门视频: {bvid}")
    elif args.source or args.bvid:
        source = args.source or args.bvid
        bvid = parse_bvid(source) if args.channel == "bilibili" or "BV" in source else source
    else:
        parser.print_help()
        return

    result = run_vertical_slice(
        bvid,
        run_dir,
        do_render=bool(args.render and not args.no_render),
        language_style=args.style,
        channel=args.channel,
        target_platforms=[x.strip() for x in args.targets.split(",") if x.strip()],
        visual_style=args.visual_style,
        generation_mode=args.generation_mode,
        character_id=args.character_id,
    )
    print("RUN_OK run_dir=%s" % run_dir)
    print("segments=%s media=%s" % (
        len(result.get("script", {}).get("segments", [])),
        "yes" if result.get("media") else "no",
    ))


if __name__ == "__main__":
    main()
