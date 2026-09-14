from __future__ import annotations

import html as html_lib
import json
import re
import time
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin

import httpx

try:
    import requests
except ImportError:  # pragma: no cover - requests is in production requirements
    requests = None

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
URL_RE = re.compile(r"https?://[^\s\]\)<>]+", re.IGNORECASE)
DOMAIN_RE = re.compile(
    r"(?:(?:(?:v|www)\.)?(?:douyin|kuaishou|xiaohongshu)\.com/|xhslink\.com/)[^\s\]\)<>]+",
    re.IGNORECASE,
)


def _request_headers() -> Dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "close",
    }


def extract_first_url(text: str) -> str:
    """从“复制打开抖音…”等分享文案或 Markdown 链接中提取真实 URL。"""
    value = html_lib.unescape(str(text or "")).replace("\\/", "/")
    match = URL_RE.search(value)
    if match:
        return match.group(0).rstrip(".,;，。！？!?)）]")
    match = DOMAIN_RE.search(value)
    if match:
        return ("https://" + match.group(0)).rstrip(".,;，。！？!?)）]")
    return ""


def parse_share_text(text: str) -> Dict[str, str]:
    """Extract author, title and description from a copied platform share message."""
    value = html_lib.unescape(str(text or "")).replace("\\/", "/").strip()
    if not value:
        return {}

    author = ""
    author_match = re.search(r"【(.+?)的作品】", value)
    if author_match:
        author = author_match.group(1).strip()

    url = extract_first_url(value)
    body = value
    if url:
        body = body.replace(url, " ")
    body = re.sub(r"^\s*[\d.]+\s*复制打开(?:抖音|快手|小红书)，?看看", "", body)
    body = re.sub(r"^\s*复制打开(?:抖音|快手|小红书)，?看看", "", body)
    if "】" in body:
        body = body.split("】", 1)[1]
    body = re.sub(
        r"\s+\d{1,2}/\d{1,2}\s+.*$",
        "",
        body,
        flags=re.DOTALL,
    )
    title = re.sub(r"\s+", " ", body).strip(" -#，。:：")

    result: Dict[str, str] = {}
    if title:
        result["title"] = title[:200]
    if author:
        result["author"] = author[:100]
    if value:
        result["description"] = value[:1000]
        result["transcript"] = value[:1000]
    return result


def is_challenge_page(html: str) -> bool:
    text = str(html or "")
    lowered = text.lower()
    return (
        "_$jsvmprt" in text
        or "/******/ (() =>" in text
        or ("<body></body>" in lowered and "javascript" in lowered)
    )


def resolve_share_url(url: str, *, timeout: float = 15.0) -> str:
    url = extract_first_url(url) or url
    try:
        final_url, _html = _fetch_http(url, timeout=timeout)
        return final_url
    except Exception:
        return url


def fetch_page(url: str, *, timeout: float = 15.0) -> tuple[str, str]:
    url = extract_first_url(url) or url
    return _fetch_http(url, timeout=timeout)


def _fetch_http(url: str, *, timeout: float = 15.0) -> tuple[str, str]:
    """Fetch a public share page with retries and a requests transport fallback."""
    headers = _request_headers()
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=timeout,
                headers=headers,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                if is_challenge_page(response.text):
                    raise RuntimeError("platform returned a JavaScript challenge page")
                return str(response.url), response.text
        except (httpx.TransportError, httpx.HTTPStatusError, RuntimeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.4 * (attempt + 1))

    try:
        if requests is None:
            raise RuntimeError("requests transport is not installed")
        session = requests.Session()
        session.headers.update(headers)
        response = session.get(url, allow_redirects=True, timeout=timeout)
        response.raise_for_status()
        if is_challenge_page(response.text):
            raise RuntimeError("platform returned a JavaScript challenge page")
        return response.url, response.text
    except Exception as exc:
        last_error = exc

    raise RuntimeError(f"share page fetch failed after retries: {last_error}") from last_error


def extract_meta(html: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    patterns = {
        "title": r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\'](.*?)["\']',
        "description": r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\'](.*?)["\']',
        "cover_url": r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\'](.*?)["\']',
        "author": r'<meta[^>]+(?:property|name)=["\'](?:author|og:site_name)["\'][^>]+content=["\'](.*?)["\']',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            out[key] = html_lib.unescape(match.group(1)).strip()
    return out


def _decode_json_blob(blob: str) -> Any:
    text = html_lib.unescape(blob).strip().rstrip(";")
    if text.startswith("JSON.parse(") and text.endswith(")"):
        text = text[len("JSON.parse("):-1]
        text = json.loads(text)
    return json.loads(text)


def extract_json_objects(html: str) -> list[Any]:
    objects: list[Any] = []
    patterns = [
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        r"<script[^>]*id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>",
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;",
        r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;",
        r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*;",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, flags=re.DOTALL | re.IGNORECASE):
            try:
                objects.append(_decode_json_blob(match.group(1)))
            except Exception:
                continue
    return objects


KEY_CANDIDATES = {
    "title": ("title", "desc", "description", "caption", "text"),
    "description": ("description", "desc", "caption", "text", "content"),
    "author": ("author", "nickname", "nickName", "name", "owner", "user_name", "userName"),
    "cover_url": ("cover", "cover_url", "coverUrl", "originCover", "dynamicCover", "image"),
    "duration_sec": ("duration", "duration_sec", "durationMs", "video_duration"),
    "source_id": ("id", "itemId", "aweme_id", "note_id", "video_id", "photoId"),
    "media_url": ("play_url", "playUrl", "download_url", "downloadUrl", "video_url", "videoUrl"),
    "transcript": ("transcript", "subtitle", "subtitle_text", "text_extra", "caption"),
}


def _walk(obj: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = path + (str(key),)
            yield child, value
            yield from _walk(value, child)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _walk(value, path + (str(index),))


def _first_by_keys(obj: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, "", [], {}):
                return obj[key]
        for value in obj.values():
            found = _first_by_keys(value, keys)
            if found not in (None, "", [], {}):
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _first_by_keys(value, keys)
            if found not in (None, "", [], {}):
                return found
    return None


def normalize_page(url: str, html: str, platform: str) -> Dict[str, Any]:
    meta = extract_meta(html)
    objects = extract_json_objects(html)
    data: Dict[str, Any] = {
        "source_url": url,
        "platform": platform,
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "author": meta.get("author", ""),
        "cover_url": meta.get("cover_url", ""),
        "raw": {"html_title": meta.get("title", ""), "json_objects": objects},
    }
    for key, candidates in KEY_CANDIDATES.items():
        for obj in objects:
            value = _first_by_keys(obj, candidates)
            if value not in (None, "", [], {}):
                data[key] = value
                break
    if not data.get("source_url"):
        data["source_url"] = url
    return data
