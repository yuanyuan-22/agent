import argparse
import json
from pathlib import Path

from forge.assets import AssetManager
from forge.config import settings
from forge.content_plan import CharacterBible
from forge.generation.character import CharacterManager
from forge.generation.manager import GenerationManager
from forge.media import render


def main() -> None:
    parser = argparse.ArgumentParser(description="用已有 script.json 直接出片（用于快速迭代渲染）")
    parser.add_argument("--script", required=True, help="script.json 路径")
    parser.add_argument("--out", default="", help="输出目录（默认取 script 所在 runs 下的 media）")
    args = parser.parse_args()

    script_path = Path(args.script)
    script = json.loads(script_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out) if args.out else script_path.parent / "media"

    storyboard_path = script_path.parent / "storyboard.json"
    if storyboard_path.exists():
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        generation = GenerationManager()
        character = CharacterManager(generation).ensure(
            CharacterBible(**(storyboard.get("character") or {})),
            script_path.parent,
        )
        storyboard["character"] = character.to_dict()
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
        script["segments"] = merged_segments
    else:
        generation = GenerationManager()

    media = render(
        script,
        out_dir,
        size=(settings.video_width, settings.video_height),
        bg=settings.video_bg,
        accent=settings.video_accent,
        fps=settings.video_fps,
        asset_manager=AssetManager(generation_manager=generation),
    )
    (script_path.parent / "media_meta.json").write_text(
        json.dumps(media, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RENDER_OK video=%s duration=%ss segments=%s" % (
        media["video"], media["duration_seconds"], media["segment_count"]))


if __name__ == "__main__":
    main()
