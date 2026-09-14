from forge.channels.bilibili import BilibiliAdapter, parse_bvid
from forge.channels import share_page
from forge.channels.douyin import DouyinAdapter
from forge.channels.kuaishou import KuaishouAdapter
from forge.channels.manual import ManualAdapter
from forge.channels.share_page import (
    extract_first_url,
    is_challenge_page,
    normalize_page,
    parse_share_text,
)
from forge.channels.xiaohongshu import XiaohongshuAdapter
from forge.source_service import SourceContentMissing, fetch_source_video


def test_platform_url_matching():
    assert BilibiliAdapter().match("https://www.bilibili.com/video/BV1wFZ8YBEt4")
    assert DouyinAdapter().match("https://v.douyin.com/abc123/")
    assert KuaishouAdapter().match("https://v.kuaishou.com/abc123")
    assert XiaohongshuAdapter().match("https://xhslink.com/abc123")
    assert parse_bvid("BV1wFZ8YBEt4") == "BV1wFZ8YBEt4"


def test_extract_url_from_douyin_share_text():
    text = (
        "8.25 复制打开抖音，看看【雪妮Barby的作品】待我如初这四个字在你这里竟如初简单 "
        "https://v.douyin.com/uvfeHq7TZZM/ 04/14 :1pm i@C.Hi Njc:/"
    )
    assert extract_first_url(text) == "https://v.douyin.com/uvfeHq7TZZM/"
    assert DouyinAdapter().match(text) is True


def test_extract_url_from_markdown_link():
    text = "[https://v.kuaishou.com/abc123](https://v.kuaishou.com/abc123)"
    assert extract_first_url(text) == "https://v.kuaishou.com/abc123"


def test_parse_share_text_keeps_author_and_title():
    text = (
        "6.97 复制打开抖音，看看【iio的作品】"
        "当初你说桂林山水甲天下，我便来到了桂林# 火车票盲盒 "
        "https://v.douyin.com/8c-c_F-T-G8/ 12/18 J@V.yT :4pm xSY:/"
    )
    parsed = parse_share_text(text)
    assert parsed["author"] == "iio"
    assert "桂林山水甲天下" in parsed["title"]
    assert "火车票盲盒" in parsed["title"]


def test_douyin_javascript_challenge_is_not_treated_as_content():
    html = '<html><head></head><body></body><script>var glb;glb._$jsvmprt=function(){}</script></html>'
    assert is_challenge_page(html) is True


def test_share_page_normalize_next_data():
    html = """
    <html><head>
      <meta property="og:title" content="测试标题">
      <meta property="og:description" content="测试简介">
      <meta property="og:image" content="https://example.com/cover.jpg">
    </head><body>
      <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"video":{"id":"123","title":"JSON标题","author":"作者A","duration":42}}}}
      </script>
    </body></html>
    """
    payload = normalize_page("https://v.douyin.com/abc", html, "douyin")
    assert payload["title"]
    assert payload["description"] == "测试简介"
    assert payload["cover_url"] == "https://example.com/cover.jpg"
    assert payload["source_id"] == "123"
    assert payload["duration_sec"] == 42


def test_manual_adapter_fallback():
    adapter = ManualAdapter("douyin", {
        "title": "手动标题",
        "description": "手动文案",
        "author": "手动作者",
    })
    source = adapter.fetch("https://example.com/video")
    assert source.platform == "douyin"
    assert source.title == "手动标题"
    assert source.transcript == "手动文案"
    assert source.transcript_mode == "manual"


def test_source_service_manual_path():
    video = fetch_source_video("auto", "https://example.com/video", manual={
        "platform": "douyin",
        "title": "手动标题",
        "transcript": "手动文案",
    })
    assert video["platform"] == "douyin"
    assert video["title"] == "手动标题"
    assert video["transcript_text"] == "手动文案"


def test_source_service_uses_share_text_when_page_fetch_fails(monkeypatch):
    class FailingAdapter:
        platform = "douyin"

        def fetch(self, url):
            raise RuntimeError("tls eof")

    monkeypatch.setattr("forge.source_service.get_adapter", lambda _value: FailingAdapter())
    video = fetch_source_video(
        "auto",
        "https://v.douyin.com/8c-c_F-T-G8/",
        manual={
            "fallback_only": True,
            "platform": "douyin",
            "title": "当初你说桂林山水甲天下，我便来到了桂林",
            "author": "iio",
            "description": "火车票盲盒",
            "transcript": "火车票盲盒去广西",
        },
    )
    assert video["title"].startswith("当初你说桂林")
    assert video["owner"] == "iio"
    assert video["transcript_text"] == "火车票盲盒去广西"
    assert video["transcript_mode"] == "share_text"


def test_source_service_rejects_empty_source_context(monkeypatch):
    class EmptyAdapter:
        platform = "douyin"

        def fetch(self, url):
            from forge.channels.base import SourceVideo

            return SourceVideo(
                platform="douyin",
                source_id="empty",
                source_url=url,
                transcript_mode="none",
            )

    monkeypatch.setattr("forge.source_service.get_adapter", lambda _value: EmptyAdapter())
    try:
        fetch_source_video("auto", "https://v.douyin.com/empty/")
    except SourceContentMissing:
        pass
    else:
        raise AssertionError("empty source context should be rejected")


def test_share_page_retries_then_uses_requests_fallback(monkeypatch):
    attempts = {"httpx": 0, "requests": 0}

    class FailingHttpxClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            attempts["httpx"] += 1
            raise share_page.httpx.TransportError("unexpected eof")

    class FakeResponse:
        status_code = 200
        url = "https://www.douyin.com/video/123"
        text = "<html>ok</html>"

        def raise_for_status(self):
            return None

    class FakeSession:
        headers = {}

        def get(self, url, **kwargs):
            attempts["requests"] += 1
            return FakeResponse()

    monkeypatch.setattr(share_page.httpx, "Client", FailingHttpxClient)
    monkeypatch.setattr(share_page.requests, "Session", FakeSession)
    monkeypatch.setattr(share_page.time, "sleep", lambda _seconds: None)

    final_url, html = share_page.fetch_page("https://v.douyin.com/abc/")

    assert attempts == {"httpx": 3, "requests": 1}
    assert final_url == "https://www.douyin.com/video/123"
    assert html == "<html>ok</html>"
