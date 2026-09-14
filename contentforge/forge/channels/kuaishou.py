import re

from .share_adapter import SharePageAdapter


class KuaishouAdapter(SharePageAdapter):
    platform = "kuaishou"
    url_patterns = (
        re.compile(r"https?://(?:www\.)?kuaishou\.com/", re.I),
        re.compile(r"https?://v\.kuaishou\.com/", re.I),
    )
