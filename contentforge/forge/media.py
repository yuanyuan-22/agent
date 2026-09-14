from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip, VideoFileClip, concatenate_videoclips
from moviepy.audio.fx import AudioLoop
from moviepy.video.fx import Crop, Loop, Resize

from forge.config import settings

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/simsun.ttc"),
]

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")


def _resolve_font() -> Path:
    for p in FONT_CANDIDATES:
        if p.exists():
            return p
    raise RuntimeError("未找到中文字体，请安装微软雅黑或黑体")


def tts(text: str, out_path: Path) -> Path:
    from forge.tools.tts import synthesize

    return synthesize(text, out_path, speed=settings.tts_speed)


def probe_seconds(path: Path) -> float:
    proc = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True)
    m = _DURATION_RE.search(proc.stderr)
    if not m:
        raise RuntimeError(f"无法读取音视频时长: {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def concat_audio(mp3s: list[Path], out_path: Path) -> Path:
    if not mp3s:
        raise RuntimeError("没有可拼接的音频")
    inputs = []
    for p in mp3s:
        inputs += ["-i", str(p)]
    n = len(mp3s)
    labels = "".join(f"[{i}:a]" for i in range(n))
    cmd = [FFMPEG, "-y", *inputs,
           "-filter_complex", f"{labels}concat=n={n}:v=0:a=1[aout]",
           "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"音频拼接失败: {proc.stderr[-500:]}")
    return out_path


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        cur = ""
        for ch in raw:
            if font.getlength(cur + ch) <= max_width or not cur:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


def _fit_font(body: str, font_path: Path, size_start: int, size_min: int,
              max_width: int, max_height: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(size_start, size_min - 1, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap(body, font, max_width)
        line_h = size * 1.45
        if len(lines) * line_h <= max_height:
            return font, lines
    font = ImageFont.truetype(str(font_path), size_min)
    return font, _wrap(body, font, max_width)


def _gradient_bg(size, top: tuple, bottom: tuple) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / h
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def _accent_art(draw: ImageDraw.ImageDraw, size: tuple, accent: tuple) -> None:
    w, h = size
    draw.ellipse([w - 260, -180, w + 160, 240], outline=accent + (60,), width=3)
    draw.rounded_rectangle([80, 200, 96, 200 + 120], radius=8, fill=accent + (255,))


def make_segment_card(script: dict, index: int, total: int, segment: dict,
                      font_path: Path, size: tuple, bg: tuple,
                      accent: tuple) -> Image.Image:
    w, h = size
    darker = tuple(max(c - 18, 0) for c in bg)
    img = _gradient_bg(size, darker, bg)
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    _accent_art(draw, size, accent)

    topic = script.get("topic") or script.get("title") or "内容分享"
    font_sm = ImageFont.truetype(str(font_path), 34)
    tag = f"第 {index}/{total} 段"
    tag_w = draw.textlength(tag, font=font_sm)
    draw.rounded_rectangle([90, 170, 90 + tag_w + 40, 238], radius=34, fill=accent + (230,))
    draw.text((110, 182), tag, font=font_sm, fill=(255, 255, 255))

    heading = (segment.get("heading") or "").strip()
    body_top = 330
    if heading:
        font_h, heading_lines = _fit_font(heading, font_path, 54, 36, w - 180, 170)
        y_h = 300
        for ln in heading_lines:
            draw.text((90, y_h), ln, font=font_h, fill=(255, 255, 255))
            y_h += int(font_h.size * 1.4)
        body_top = y_h + 20

    body_max_h = 1250
    body_w = w - 180
    text = segment.get("text") or ""
    font_b, lines = _fit_font(text, font_path, 70, 44, body_w, body_max_h)
    line_h = int(font_b.size * 1.45)
    y = body_top
    for ln in lines:
        draw.text((90, y), ln, font=font_b, fill=(235, 240, 248))
        y += line_h

    font_brand = ImageFont.truetype(str(font_path), 30)
    draw.text((90, h - 150), topic, font=font_brand, fill=(170, 180, 200))
    bar_y = h - 92
    bar_w = w - 180
    draw.rounded_rectangle([90, bar_y, 90 + bar_w, bar_y + 14], radius=7, fill=(255, 255, 255, 40))
    fill_w = int(bar_w * index / total)
    if fill_w > 0:
        draw.rounded_rectangle([90, bar_y, 90 + fill_w, bar_y + 14], radius=7, fill=accent + (255,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


def make_cover(script: dict, font_path: Path, size: tuple, bg: tuple,
               accent: tuple) -> Image.Image:
    w, h = size
    img = _gradient_bg(size, bg, tuple(max(c - 30, 0) for c in bg))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    _accent_art(draw, size, accent)

    cover_text = script.get("cover_text") or script.get("title") or "新内容"
    font_c, _ = _fit_font(cover_text, font_path, 130, 70, w - 160, 420)
    draw.text((90, 620), cover_text, font=font_c, fill=(255, 255, 255))

    title = script.get("title") or ""
    font_t, lines = _fit_font(title, font_path, 52, 36, w - 180, 200)
    y = 1150
    for ln in lines[:3]:
        draw.text((90, y), ln, font=font_t, fill=(205, 215, 230))
        y += int(font_t.size * 1.4)

    font_brand = ImageFont.truetype(str(font_path), 32)
    text = "ContentForge · AI 原创解说"
    tw = draw.textlength(text, font=font_brand)
    draw.text(((w - tw) / 2, h - 130), text, font=font_brand, fill=(150, 160, 180))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


def _fit_clip(clip, size: tuple):
    w, h = size
    cw, ch = clip.size
    scale = max(w / max(cw, 1), h / max(ch, 1))
    resized = clip.with_effects([Resize(scale)])
    return resized.with_effects([
        Crop(x_center=resized.w / 2, y_center=resized.h / 2, width=w, height=h)
    ])


def _caption_overlay(segment: dict, font_path: Path, size: tuple) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    text = (segment.get("caption") or segment.get("text") or "").strip()
    if not text:
        return img
    font, lines = _fit_font(text, font_path, 56, 36, w - 160, 360)
    line_h = int(font.size * 1.35)
    block_h = line_h * len(lines) + 60
    top = h - block_h - 170
    draw.rounded_rectangle([60, top, w - 60, top + block_h], radius=24,
                           fill=(5, 12, 24, 185))
    y = top + 30
    for line in lines:
        draw.text((90, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h
    return img


def _character_overlay(segment: dict, size: tuple) -> Image.Image | None:
    character = segment.get("character") or {}
    path = character.get("base_image_path") or ""
    if not segment.get("show_character", True) or not path or not Path(path).exists():
        return None
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    avatar = Image.open(path).convert("RGBA")
    target_w = int(w * 0.30)
    target_h = int(avatar.height * target_w / max(avatar.width, 1))
    avatar = avatar.resize((target_w, target_h), Image.Resampling.LANCZOS)
    img.alpha_composite(avatar, (w - target_w - 60, h - target_h - 220))
    return img


def _pick_music() -> Path | None:
    root = settings.music_dir
    if not root.exists():
        return None
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac"}:
            return path
    return None


def render(script: dict, out_dir: Path,
           size: tuple, bg: tuple, accent: tuple, fps: int,
           asset_manager=None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    font_path = _resolve_font()

    segments = script.get("segments") or []
    if not segments:
        raise RuntimeError("脚本没有 segments")

    seg_dir = out_dir / "seg"
    seg_dir.mkdir(parents=True, exist_ok=True)

    mp3s: list[Path] = []
    durations: list[float] = []
    for i, seg in enumerate(segments, start=1):
        text = (seg.get("text") or "").strip()
        if not text:
            raise RuntimeError(f"第 {i} 段文本为空")
        mp3 = seg_dir / f"{i:02d}.mp3"
        if not (mp3.exists() and mp3.stat().st_size > 0):
            tts(text, mp3)
        mp3s.append(mp3)
        durations.append(probe_seconds(mp3) + 0.35)

    audio_path = concat_audio(mp3s, seg_dir / "full.aac")

    total = len(segments)
    used_assets: set[str] = set()
    scene_assets = []
    clips = []
    for i, seg in enumerate(segments, start=1):
        duration = durations[i - 1]
        asset = asset_manager.resolve(seg, out_dir, used_assets) if asset_manager else None
        scene_assets.append(asset.to_dict() if asset else {})

        if asset and Path(asset.path).exists():
            try:
                if asset.kind == "video":
                    base = VideoFileClip(asset.path).without_audio()
                    if base.duration < duration:
                        base = base.with_effects([Loop(duration=duration)])
                    else:
                        base = base.subclipped(0, duration)
                    base = _fit_clip(base, size)
                else:
                    base = _fit_clip(ImageClip(asset.path).with_duration(duration), size)
                overlay = ImageClip(np.asarray(_caption_overlay(seg, font_path, size))).with_duration(duration)
                layers = [base, overlay]
                character = _character_overlay(seg, size)
                if character is not None:
                    layers.append(ImageClip(np.asarray(character)).with_duration(duration))
                clip = CompositeVideoClip(layers, size=size).with_duration(duration)
                clips.append(clip)
                continue
            except Exception:
                scene_assets[-1] = {"error": "asset_load_failed", "path": asset.path}

        card = make_segment_card(script, i, total, seg, font_path, size, bg, accent)
        clip = ImageClip(np.asarray(card)).with_duration(duration)
        if i % 2 == 0:
            def _scale(t: float, duration: float = duration) -> float:
                return 1.0 + 0.025 * t / max(duration, 0.1)

            clip = clip.with_effects([
                Resize(_scale),
                Crop(x_center=clip.w / 2, y_center=clip.h / 2,
                     width=clip.w, height=clip.h),
            ])
        clips.append(clip)

    video = concatenate_videoclips(clips, method="chain").with_fps(fps)
    voice_audio = AudioFileClip(str(audio_path))
    total_dur = sum(durations)
    music_path = _pick_music()
    if music_path:
        try:
            music_audio = (
                AudioFileClip(str(music_path))
                .with_effects([AudioLoop(duration=total_dur)])
                .with_volume_scaled(0.12)
            )
            video = video.with_audio(CompositeAudioClip([voice_audio, music_audio]))
        except Exception:
            video = video.with_audio(voice_audio)
    else:
        video = video.with_audio(voice_audio)

    video_path = out_dir / "final.mp4"
    video.write_videofile(str(video_path), fps=fps, codec="libx264",
                          audio_codec="aac", preset="veryfast", logger=None)

    cover = make_cover(script, font_path, size, bg, accent)
    cover_path = out_dir / "cover.png"
    cover.save(cover_path)

    from forge.video_manifest import (
        build_generation_manifest,
        build_manifest,
        write_manifest,
        write_srt,
    )

    scenes = []
    for i, seg in enumerate(segments):
        scenes.append({
            **seg,
            "duration": durations[i],
            "caption": seg.get("caption") or seg.get("text") or "",
            "asset": scene_assets[i],
        })
    manifest = build_manifest(script, scenes, out_dir=out_dir, size=size, fps=fps)
    manifest_path = write_manifest(manifest, out_dir)
    srt_path = write_srt(manifest, out_dir)
    generation_manifest = build_generation_manifest(scenes)
    generation_path = out_dir / "generation_manifest.json"
    import json

    generation_path.write_text(
        json.dumps(generation_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    from forge.visual_reviewer import review_visuals

    visual_review = review_visuals(scenes)
    visual_review_path = out_dir / "visual_review.json"
    visual_review_path.write_text(
        json.dumps(visual_review, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "video": str(video_path),
        "cover": str(cover_path),
        "manifest": str(manifest_path),
        "captions": str(srt_path),
        "generation_manifest": str(generation_path),
        "visual_review": str(visual_review_path),
        "seg_audios": [str(p) for p in mp3s],
        "full_audio": str(audio_path),
        "duration_seconds": round(total_dur, 2),
        "segment_count": total,
    }
