REFUSAL = (
    "من اینجا فقط گفتگو می‌کنم و کد یا تصویر نمی‌سازم. "
    "اگر خواستی، دربارهٔ ساختن چیزها با هم حرف می‌زنیم."
)

_BT = chr(96) * 3
_MARKERS = (
    _BT,
    "~~~",
    chr(33) + "[",
    "<svg",
    "<html",
    "<script",
    "<!doctype",
    "data:image/",
)


def conversation_only(reply: str) -> str:
    lowered = reply.lower()
    if any(m in lowered for m in _MARKERS):
        return REFUSAL
    return reply


import re as _re

BUILD_REFUSAL = "فعلاً فقط در حالت گفتگو هستم و چیزی نمی‌سازم. اگر خواستی درباره‌اش حرف بزنیم، بگو."

_BUILD_PATTERNS = (
    r"کد\s*(?:بنویس|بزن|درست\s*کن)",
    r"(?:بساز|درست\s*کن|طراحی\s*کن|پیاده\s*سازی\s*کن)",
    r"(?:فایل|پروژه|اپ|برنامه|بازی|سایت)\s*(?:بساز|درست|بنویس)",
    r"\b(?:write|create|build|generate|make)\b.{0,30}\b(?:code|script|app|file|game|website|program)\b",
)


def is_build_request(text: str) -> bool:
    normalized = text.replace("\u200c", " ").lower()
    return any(_re.search(p, normalized) for p in _BUILD_PATTERNS)
