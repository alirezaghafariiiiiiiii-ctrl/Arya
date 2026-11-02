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
