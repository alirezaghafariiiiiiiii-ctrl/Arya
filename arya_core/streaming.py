"""گفت‌وگوی جریانی (streaming) برای ARIA."""
from __future__ import annotations

from collections.abc import Iterator

from .guard import REFUSAL, guard_stream

_PROVIDER_ERROR = "خطا در ارتباط با مدل: {error}"
_EMPTY_REPLY = "جوابی از مدل نگرفتم، دوباره بگو."


def _as_chunks(raw) -> Iterator[str]:
    if isinstance(raw, str):
        yield raw
        return
    for chunk in raw:
        if chunk:
            yield chunk


def stream_response(engine, user_text: str) -> Iterator[str]:
    text = str(user_text).strip()
    provider = engine.provider

    if not text or text.startswith("/") or provider is None or not hasattr(provider, "chat"):
        yield engine.generate_response(user_text)
        return

    user_message = engine._message("user", text)
    if engine.session_store is not None and engine.session_id is not None:
        engine.session_store.add_message(engine.session_id, "user", text)
    engine.history.append(user_message)

    messages = [{"role": m.role, "content": m.content} for m in engine.history]
    system_prompt = engine._build_system_prompt(text)

    parts: list[str] = []
    blocked = False
    try:
        if hasattr(provider, "chat_stream"):
            raw = provider.chat_stream(system_prompt, messages)
        else:
            raw = provider.chat(system_prompt, messages)
        for piece in guard_stream(_as_chunks(raw)):
            if piece == REFUSAL:
                blocked = True
            parts.append(piece)
            yield piece
    except Exception as error:
        yield _PROVIDER_ERROR.format(error=error)
        return

    reply = REFUSAL if blocked else "".join(parts).strip()
    if not reply:
        yield _EMPTY_REPLY
        return

    if engine.session_store is not None and engine.session_id is not None:
        engine.session_store.add_message(engine.session_id, "assistant", reply)
    engine.history.append(engine._message("assistant", reply))

    try:
        engine._extract_facts(text)
    except Exception:
        pass
