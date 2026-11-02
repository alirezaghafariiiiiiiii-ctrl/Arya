REFUSAL = (
    "I can only chat here, not write code or images. "
    "Ask me about building things if you like."
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
