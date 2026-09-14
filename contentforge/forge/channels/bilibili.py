from __future__ import annotations

import re
import time

import httpx

from forge.config import settings
from .base import ChannelAdapter, SourceVideo

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")


class BiliError(RuntimeError):
    pass


class BiliClient:
    def __init__(self):
        self.timeout = settings.bili_timeout
        self.retries = settings.bili_retries
        self.s = httpx.Client(
            headers={
                "User-Agent": UA,
                "Referer": "https://www.bilibili.com",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.bilibili.com",
            },
            timeout=self.timeout,
            follow_redirects=True,
        )
        self._prime()

    def _prime(self) -> None:
        try:
            self.s.get("https://www.bilibili.com")
        except httpx.HTTPError:
            pass

    def _get_json(self, url: str, params: dict | None = None) -> dict:
        last = None
        for i in range(self.retries):
            try:
                resp = self.s.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
                code = body.get("code")
                if code == 0:
                    return body
                if code == -412:
                    wait = 2 ** i + 2
                    time.sleep(wait)
                    last = BiliError(f"B站风控(-412): {url}")
                    continue
                raise BiliError(f"B站接口错误 code={code} msg={body.get('message')} url={url}")
            except (httpx.HTTPError, ValueError) as e:
                last = BiliError(f"B站请求失败: {e}")
                time.sleep(1 + i)
        raise last or BiliError(f"B站请求失败: {url}")

    def view(self, bvid: str) -> dict:
        data = self._get_json("https://api.bilibili.com/x/web-interface/view",
                              {"bvid": bvid})
        return data.get("data") or {}

    def subtitle_list(self, bvid: str, cid: int) -> list[dict]:
        data = self._get_json("https://api.bilibili.com/x/player/v2",
                              {"bvid": bvid, "cid": cid})
        return (data.get("data") or {}).get("subtitle", {}).get("subtitles") or []

    def fetch_subtitle_text(self, bvid: str, cid: int, lan: str = "") -> str:
        subs = self.subtitle_list(bvid, cid)
        if not subs:
            return ""
        pick = None
        if lan:
            pick = next((s for s in subs if s.get("lan") == lan), None)
        pick = pick or subs[0]
        url = pick.get("subtitle_url") or ""
        if url.startswith("//"):
            url = "https:" + url
        if not url:
            return ""
        try:
            resp = self.s.get(url, headers={"Referer": f"https://www.bilibili.com/video/{bvid}"})
            resp.raise_for_status()
            body = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise BiliError(f"字幕拉取失败: {e}")
        lines = (body.get("body") or []) if isinstance(body, dict) else []
        text = "\n".join(item.get("content", "").strip() for item in lines if item.get("content"))
        return text

    def audio_url(self, bvid: str, cid: int) -> str:
        cands = self.audio_candidates(bvid, cid)
        if not cands:
            raise BiliError(f"无法获取音频流: {bvid}")
        return cands[0]

    def audio_candidates(self, bvid: str, cid: int) -> list[str]:
        data = self._get_json("https://api.bilibili.com/x/player/playurl",
                              {"bvid": bvid, "cid": cid, "qn": 16, "fnval": 16, "fourk": 1})
        audio = (data.get("data") or {}).get("dash", {}).get("audio") or []
        urls: list[str] = []
        for a in audio:
            candidates = [a.get("baseUrl"), a.get("base_url")]
            candidates += list(a.get("backupUrl") or [])
            candidates += list(a.get("backup_url") or [])
            for u in candidates:
                if isinstance(u, str) and u.strip():
                    urls.append(u.strip())
        seen: set[str] = set()
        ordered: list[str] = []
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            if "mcdn" in u:
                ordered.append(u)   # PCDN 节点不稳定，放最后
            else:
                ordered.insert(0, u)  # 官方 upos 源优先
        return ordered

    def download_audio(self, bvid: str, cid: int, dest_dir, cap_seconds: int) -> str:
        import subprocess
        import time
        from pathlib import Path

        import imageio_ffmpeg

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        wav = dest_dir / f"{bvid}_{cid}_cap{cap_seconds}.wav"
        if wav.exists() and wav.stat().st_size > 0:
            return str(wav)

        candidates = self.audio_candidates(bvid, cid)
        if not candidates:
            raise BiliError(f"无法获取音频流: {bvid}")
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        headers = (
            f"User-Agent: {UA}\r\n"
            "Referer: https://www.bilibili.com\r\n"
            "Accept: */*\r\n"
        )
        last_err = ""
        max_tries = 5
        for i, url in enumerate(candidates[:max_tries]):
            wav.unlink(missing_ok=True)
            cmd = [ffmpeg, "-y", "-rw_timeout", "10000000",
                   "-headers", headers, "-i", url,
                   "-t", str(cap_seconds),
                   "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            except subprocess.TimeoutExpired:
                last_err = f"源{i + 1}下载超时(>90s)"
                continue
            if proc.returncode == 0 and wav.exists() and wav.stat().st_size > 0:
                return str(wav)
            last_err = proc.stderr[-400:]
            if i < len(candidates) - 1:
                time.sleep(1)
        wav.unlink(missing_ok=True)
        raise BiliError(f"音频流全部下载失败(尝试{min(max_tries, len(candidates))}个源): {last_err}")

    def fetch(self, bvid: str, with_subtitle: bool = True) -> dict:
        info = self.view(bvid)
        if not info:
            raise BiliError(f"视频不存在或不可访问: {bvid}")
        cid = int(info.get("cid") or 0)
        stat = info.get("stat") or {}
        subtitle_text = self.fetch_subtitle_text(bvid, cid) if with_subtitle and cid else ""
        return {
            "bvid": bvid,
            "aid": info.get("aid"),
            "cid": cid,
            "title": info.get("title", ""),
            "desc": info.get("desc", ""),
            "tname": info.get("tname", ""),
            "owner": (info.get("owner") or {}).get("name", ""),
            "pic": info.get("pic", ""),
            "pubdate": info.get("pubdate"),
            "duration": info.get("duration"),
            "stat": {
                "view": stat.get("view", 0),
                "danmaku": stat.get("danmaku", 0),
                "reply": stat.get("reply", 0),
                "favorite": stat.get("favorite", 0),
                "coin": stat.get("coin", 0),
                "share": stat.get("share", 0),
                "like": stat.get("like", 0),
            },
            "subtitle_text": subtitle_text,
        }

    def ranking(self, rid: int = 0, ps: int = 20) -> list[dict]:
        data = self._get_json("https://api.bilibili.com/x/web-interface/ranking/v2",
                              {"rid": rid, "type": "all", "ps": ps})
        return (data.get("data") or {}).get("list") or []

    def trending(self, limit: int = 10) -> list[dict]:
        result = []
        for item in self.ranking(rid=0, ps=max(limit * 2, 30))[:limit]:
            bvid = item.get("bvid")
            if not bvid:
                continue
            stat = item.get("stat") or {}
            result.append({
                "bvid": bvid,
                "title": item.get("title", ""),
                "tname": item.get("tname", ""),
                "owner": (item.get("owner") or {}).get("name", ""),
                "stat": {
                    "view": stat.get("view", 0),
                    "like": stat.get("like", 0),
                    "coin": stat.get("coin", 0),
                },
            })
        return result

    def close(self) -> None:
        self.s.close()


def parse_bvid(url_or_bvid: str) -> str:
    match = BV_RE.search(url_or_bvid)
    if not match:
        raise BiliError(f"无法解析 BVID: {url_or_bvid}")
    return match.group(0)


class BilibiliAdapter(ChannelAdapter):
    platform = "bilibili"

    def match(self, url: str) -> bool:
        return bool(BV_RE.search(url or "")) or "bilibili.com" in (url or "")

    def fetch(self, url: str, *, with_transcript: bool = True) -> SourceVideo:
        bvid = parse_bvid(url)
        client = BiliClient()
        try:
            raw = client.fetch(bvid, with_subtitle=with_transcript)
        finally:
            client.close()
        transcript = str(raw.get("subtitle_text") or "")
        return SourceVideo(
            platform=self.platform,
            source_id=bvid,
            source_url=f"https://www.bilibili.com/video/{bvid}",
            title=str(raw.get("title") or ""),
            author=str(raw.get("owner") or ""),
            description=str(raw.get("desc") or ""),
            cover_url=str(raw.get("pic") or ""),
            duration_sec=float(raw.get("duration") or 0),
            stats=dict(raw.get("stat") or {}),
            transcript=transcript,
            transcript_mode="cc" if transcript else "none",
            raw=raw,
        )

    def trending(self, limit: int = 10) -> list[dict]:
        client = BiliClient()
        try:
            return client.trending(limit=limit)
        finally:
            client.close()
