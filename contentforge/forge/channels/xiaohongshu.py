import re

from .share_adapter import SharePageAdapter


class XiaohongshuAdapter(SharePageAdapter):
    platform = "xiaohongshu"
    url_patterns = (
        re.compile(r"https?://(?:www\.)?xiaohongshu\.com/", re.I),
        re.compile(r"https?://xhslink\.com/", re.I),
    )
