from __future__ import annotations

from pathlib import Path
import subprocess

import imageio_ffmpeg

from forge.channels.bilibili import BiliClient, BiliError
from forge.config import settings
from forge.tools.asr import transcribe


def _meaningful_len(text: str) -> int:
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    alpha = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return cjk + alpha


def transcript_cache() -> Path:
    p = settings.data_dir / "transcripts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_transcript(client: BiliClient, video: dict, cache_dir: Path | None = None,
                   on_status=None) -> dict:
    cache_dir = cache_dir or transcript_cache()
    cc = (video.get("subtitle_text") or "").strip()
    if cc:
        return {"text": cc, "mode": "cc", "bvid": video.get("bvid")}

    bvid = video.get("bvid")
    cid = int(video.get("cid") or 0)
    if settings.asr_enabled and bvid and cid:
        cache_dir.mkdir(parents=True, exist_ok=True)
        wav = cache_dir / f"{bvid}_{cid}_cap{settings.asr_max_seconds}.wav"
        if not wav.exists():
            if on_status:
                on_status(f"正在下载音频(前{settings.asr_max_seconds}s, 最多尝试5个源)...")
            try:
                wav = Path(client.download_audio(bvid, cid, cache_dir, settings.asr_max_seconds))
                if on_status:
                    on_status("音频就绪, 正在ASR转写...")
            except BiliError as e:
                return {"text": "", "mode": "none", "bvid": bvid, "error": str(e)}
        else:
            if on_status:
                on_status("命中音频缓存, 正在ASR转写...")
        try:
            text = transcribe(str(wav))
            if _meaningful_len(text) < 12:
                if on_status:
                    on_status("该视频以音乐/无人声为主，转录内容过少，将基于标题与简介创作")
                return {"text": "", "mode": "low", "bvid": bvid}
            if on_status:
                on_status(f"ASR完成, 转录{len(text)}字")
            return {"text": text, "mode": "asr", "bvid": bvid}
        except Exception as e:
            return {"text": "", "mode": "error", "bvid": bvid, "error": str(e)}

    return {"text": "", "mode": "none", "bvid": bvid}


def get_transcript_from_media_url(media_url: str, cache_key: str,
                                  cache_dir: Path | None = None,
                                  on_status=None) -> dict:
    """对公开 media_url 做低频下载 + ASR；失败返回 none。"""
    if not (settings.asr_enabled and media_url):
        return {"text": "", "mode": "none", "cache_key": cache_key}
    cache_dir = cache_dir or transcript_cache()
    cache_dir.mkdir(parents=True, exist_ok=True)
    wav = cache_dir / f"{cache_key}_cap{settings.asr_max_seconds}.wav"
    if not wav.exists() or wav.stat().st_size == 0:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg, "-y", "-rw_timeout", "10000000",
            "-i", media_url,
            "-t", str(settings.asr_max_seconds),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return {"text": "", "mode": "error", "cache_key": cache_key, "error": "media download timeout"}
        if proc.returncode != 0 or not wav.exists() or wav.stat().st_size == 0:
            return {"text": "", "mode": "error", "cache_key": cache_key, "error": proc.stderr[-300:]}
    try:
        if on_status:
            on_status("音频就绪, 正在ASR转写...")
        text = transcribe(str(wav))
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "mode": "error", "cache_key": cache_key, "error": str(exc)}
    if _meaningful_len(text) < 12:
        return {"text": "", "mode": "low", "cache_key": cache_key}
    return {"text": text, "mode": "asr", "cache_key": cache_key}
