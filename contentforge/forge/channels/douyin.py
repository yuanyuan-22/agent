import re

from .share_adapter import SharePageAdapter


class DouyinAdapter(SharePageAdapter):
    platform = "douyin"
    url_patterns = (
        re.compile(r"https?://(?:www\.)?douyin\.com/", re.I),
        re.compile(r"https?://v\.douyin\.com/", re.I),
    )
