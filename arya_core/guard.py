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


_STREAM_MARKERS = ("```", "~~~", "![", "<svg", "<html", "<script", "<!doctype", "data:image/")
_STREAM_HOLD = max(len(m) for m in _STREAM_MARKERS) - 1


def guard_stream(chunks):
    """فیلتر خروجی برای پاسخ جریانی؛ چند نویسه‌ی آخر را نگه می‌دارد تا نشانه‌ی بین دو تکه هم گرفته شود."""
    buffer = ""
    for chunk in chunks:
        buffer += chunk
        if any(m in buffer.lower() for m in _STREAM_MARKERS):
            yield REFUSAL
            return
        if len(buffer) > _STREAM_HOLD:
            yield buffer[:-_STREAM_HOLD]
            buffer = buffer[-_STREAM_HOLD:]
    if buffer:
        yield buffer


_BUILD_PATTERNS = _BUILD_PATTERNS + (
    r"(?:\u0639\u06a9\u0633|\u062a\u0635\u0648\u06cc\u0631|\u0646\u0642\u0627\u0634\u06cc|\u0641\u06cc\u0644\u0645|\u0648\u06cc\u062f\u06cc\u0648|\u0648\u06cc\u062f\u0626\u0648|\u0627\u0646\u06cc\u0645\u06cc\u0634\u0646|\u0644\u0648\u06af\u0648|\u067e\u0648\u0633\u062a\u0631|\u06a9\u0627\u0631\u06cc\u06a9\u0627\u062a\u0648\u0631)\s*(?:\S+\s+){0,4}?(?:\u0628\u0633\u0627\u0632|\u0628\u06a9\u0634|\u0631\u0633\u0645\s*\u06a9\u0646|\u062a\u0648\u0644\u06cc\u062f\s*\u06a9\u0646|\u062f\u0631\u0633\u062a\s*\u06a9\u0646|\u0637\u0631\u0627\u062d\u06cc\s*\u06a9\u0646|\u0627\u06cc\u062c\u0627\u062f\s*\u06a9\u0646)(?![\u0621-\u06ff])",
    r"(?:\u0628\u0627\u0632\u06cc|\u0631\u0628\u0627\u062a|\u0627\u0633\u06a9\u0631\u06cc\u067e\u062a|\u0633\u0627\u06cc\u062a|\u0627\u067e\u0644\u06cc\u06a9\u06cc\u0634\u0646|\u0627\u067e|\u062a\u0627\u0628\u0639|\u06a9\u0644\u0627\u0633|\u0646\u0631\u0645 \u0627\u0641\u0632\u0627\u0631|\u0648\u0628 \u0633\u0627\u06cc\u062a)\s*(?:\S+\s+){0,4}?(?:\u0628\u0646\u0648\u06cc\u0633|\u0628\u0633\u0627\u0632|\u062f\u0631\u0633\u062a\s*\u06a9\u0646|\u062a\u0648\u0644\u06cc\u062f\s*\u06a9\u0646|\u0637\u0631\u0627\u062d\u06cc\s*\u06a9\u0646|\u067e\u06cc\u0627\u062f\u0647\s*\u0633\u0627\u0632\u06cc\s*\u06a9\u0646)(?![\u0621-\u06ff])",
    r"\u06a9\u062f\s*(?:\S+\s+){0,4}?(?:\u0628\u0646\u0648\u06cc\u0633|\u0628\u062f\u0647)(?![\u0621-\u06ff])",
    r"\u06a9\u062f\s*\u0628\u0632\u0646(?![\u0621-\u06ff])",
    r"\b(?:draw|paint|generate|create|make|render|design)\b.{0,30}\b(?:images?|pictures?|photos?|videos?|logos?|animations?|posters?|drawings?|illustrations?)\b",
    r"\b(?:write|build|code|program)\b.{0,30}\b(?:function|class|bot|script|app|game|website)\b",
)
