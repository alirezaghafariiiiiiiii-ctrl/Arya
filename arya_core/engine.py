from __future__ import annotations

from .guard import conversation_only, is_build_request, BUILD_REFUSAL

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence

from .config import PERSONA_PATH
from .memory import MemoryStore
from .persona import Persona
from .providers import Provider, ProviderError
from .sessions import SessionStore

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "نامت آریا است؛ دستیار هوشمند فارسی‌زبان با حافظه‌ی پایدار. "
    "صمیمی، مستقیم و محترمانه باش و از تعارف اضافه بپرهیز. "
    "کوتاه پاسخ بده، مگر اینکه توضیح بیشتری خواسته شود. "
    "با همدلی موقعیت کاربر را درک کن و سؤالش را بی‌دلیل تکرار نکن. "
    "صادق باش؛ اگر چیزی را نمی‌دانی، صریح بگو «نمی‌دانم» و حدس نزن یا با «شاید» ابهام نساز. "
    "در گفت‌وگوی عادی همیشه کاربر را با «تو» خطاب کن؛ از «شما» فقط در موقعیت رسمی استفاده کن. "
    "مثلاً بگو «چطور می‌تونم کمکت کنم؟» نه «چطور می‌توانم به شما کمک کنم؟». "
    "وقتی fact تازه‌ای درباره‌ی کاربر یاد می‌گیری، فقط یک بار کوتاه مثل «یادم می‌مونه» تأییدش کن."
)

MEMORY_INSTRUCTIONS = 'اطلاعات ذخیره\u200cشده درباره\u200cی کاربر (فقط وقتی به سؤالش مربوط است از آن\u200cها استفاده کن؛ در سلام و گفتگوی عادی اشاره نکن):\n{memories}\nضمیر «من» در این اطلاعات یعنی کاربر؛ درباره\u200cاش با «تو» حرف بزن، مثلاً «اهل شیراز هستم» را بگو «اهل شیراز هستی». اگر اطلاعاتی نیست، بگو نمی\u200cدانی و چیزی نساز.'

FACT_EXTRACTION_PROMPT = """این پیام را بررسی کن. آیا حاوی اطلاعات ماندنی و صریح درباره‌ی خود کاربر است
(نام، شهر، شغل، علاقه، ترجیح یا واقعیت شخصی)؟

فقط مواردی را استخراج کن که کاربر به‌روشنی درباره‌ی خودش بیان کرده است.
از سؤال، فرض، احتمال، نقل‌قول، داستان یا جمله‌ی منفی واقعیت شخصی استنباط نکن.
هر fact را به‌صورت جمله‌ای کامل و مستقل بنویس؛ فقط یک نام یا واژه‌ی جداافتاده ننویس.
برای مثال، «اسم من رضاست» را به شکل «FACT: نام کاربر رضاست» بنویس.
اگر اطمینان بالا نداری، فقط بنویس: NO_FACT

اگر fact قطعی وجود دارد، فقط به این شکل جواب بده (هر fact در یک خط):
FACT: ...

اگر fact قطعی وجود ندارد، فقط بنویس: NO_FACT
"""

NO_MODEL_MESSAGE = (
    "هنوز مدل زبانی‌ای به ARIA وصل نشده. دستورهای حافظه "
    "(/remember، /memories، /forget) کار می‌کنند؛ /help را ببین."
)

HELP_TEXT = """دستورها:
/remember <متن>   ذخیره یک خاطره
/memories         نمایش همه خاطرات
/forget <شماره>   حذف یک خاطره
/count            تعداد خاطرات
/reset            پاک کردن تاریخچه گفتگو (حافظه دائمی دست نمی‌خورد)
/help             همین راهنما"""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str
    timestamp: datetime


class ChatProvider(Protocol):
    def generate(self, messages: Sequence[ChatMessage]) -> str:
        ...


class NoProviderConfiguredError(RuntimeError):
    pass


def _warm_up(memory):
    try:
        memory._get_model()
    except Exception:
        pass


class ConversationEngine:
    """Conversation engine with persistent memory and memory commands."""

    def __init__(
        self,
        provider: Provider | ChatProvider | None = None,
        memory: MemoryStore | str | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_recalled: int = 5,
        max_history: int = 20,
        *,
        personality: str | None = None,
        history_limit: int | None = None,
        session_store: SessionStore | None = None,
        session_id: str | None = None,
    ):
        if isinstance(memory, str):
            # Preserve the former positional personality argument.
            if personality is not None:
                raise TypeError("personality was provided more than once")
            personality = memory
            memory = None
            if isinstance(system_prompt, int):
                max_history = system_prompt
                system_prompt = DEFAULT_SYSTEM_PROMPT

        if history_limit is not None:
            max_history = history_limit
        if max_history < 1:
            raise ValueError("max_history must be at least 1")
        if max_recalled < 0:
            raise ValueError("max_recalled cannot be negative")

        self.provider = provider
        self.memory = memory if isinstance(memory, MemoryStore) else MemoryStore()
        _warm_up(self.memory)
        self.persona = Persona(PERSONA_PATH) if PERSONA_PATH.exists() else None
        self.base_system_prompt = (
            personality.strip()
            if personality is not None
            else (
                ""
                if self.persona is not None and system_prompt == DEFAULT_SYSTEM_PROMPT
                else system_prompt.strip()
            )
        )
        self.max_recalled = max_recalled
        self.max_history = max_history
        self.history: deque[ChatMessage] = deque(maxlen=max_history)
        self.session_store = session_store
        self.session_id = session_id
        if session_id is not None and session_store is None:
            raise ValueError("session_id requires a session_store")
        if session_store is not None:
            if self.session_id is not None and not session_store.has_session(
                self.session_id
            ):
                raise ValueError(f"Unknown session: {self.session_id}")
            if self.session_id is None:
                self.session_id = session_store.get_latest_session()
            if self.session_id is None:
                self.session_id = session_store.create_session()
            for message in session_store.get_messages(
                self.session_id, limit=max_history
            ):
                self.history.append(self._message(message["role"], message["content"]))

    def _message(self, role: str, content: str) -> ChatMessage:
        if role not in {"system", "user", "assistant"}:
            raise ValueError("Invalid message role")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Message cannot be empty")
        return ChatMessage(
            role=role,
            content=content.strip(),
            timestamp=datetime.now(timezone.utc),
        )

    def set_provider(self, provider: Provider | ChatProvider) -> None:
        self.provider = provider

    def get_history(self) -> tuple[ChatMessage, ...]:
        return tuple(self.history)

    def reset(self) -> None:
        """Clear conversation history without deleting persistent memories."""
        self.history.clear()

    def generate_response(self, user_text: str) -> str:
        text = user_text.strip()
        if not text:
            return "پیامی ننوشتی."
        if text.startswith("/"):
            return self._handle_command(text)
        if self.provider is None:
            return NO_MODEL_MESSAGE

        user_message = self._message("user", text)
        if is_build_request(text):
            return BUILD_REFUSAL

        if self.session_store is not None and self.session_id is not None:
            self.session_store.add_message(self.session_id, "user", text)
        self.history.append(user_message)

        try:
            self._extract_facts(text)
            if hasattr(self.provider, "chat"):
                reply = self.provider.chat(
                    self._build_system_prompt(text),
                    [
                        {"role": message.role, "content": message.content}
                        for message in self.history
                    ],
                )
            else:
                messages = []
                if self.base_system_prompt:
                    messages.append(self._message("system", self._build_system_prompt(text)))
                messages.extend(self.history)
                reply = self.provider.generate(tuple(messages))
        except ProviderError as error:
            return f"خطا در اتصال به مدل: {error}"

        if not isinstance(reply, str) or not reply.strip():
            raise RuntimeError("Provider returned an invalid response")

        reply = conversation_only(reply)
        assistant_message = self._message("assistant", reply)
        if self.session_store is not None and self.session_id is not None:
            self.session_store.add_message(
                self.session_id, "assistant", reply.strip()
            )
        self.history.append(assistant_message)
        return reply.strip()

    def _extract_facts(self, user_text: str) -> None:
        if _looks_like_junk(user_text):
            return
        if hasattr(self.provider, "chat"):
            import inspect
            extra = {}
            if "max_tokens" in inspect.signature(self.provider.chat).parameters:
                extra["max_tokens"] = 80
            result = self.provider.chat(
                FACT_EXTRACTION_PROMPT,
                [{"role": "user", "content": user_text}],
                **extra,
            )
        else:
            result = self.provider.generate(
                (
                    self._message("system", FACT_EXTRACTION_PROMPT),
                    self._message("user", user_text),
                )
            )

        facts = _parse_facts(result)
        if facts is None:
            logger.warning("Fact extraction returned an invalid format; no facts saved")
            return

        for fact in facts:
            if _fact_is_grounded(fact, user_text):
                self.memory.add(fact)

    def _build_system_prompt(self, user_text: str) -> str:
        recalled = [] if _is_smalltalk(user_text) else self.memory.search(user_text, limit=self.max_recalled)
        memories = (
            "\n".join(f"- {item.text}" for item in recalled)
            if recalled
            else "دانسته‌ی مرتبطی درباره‌ی این سؤال پیدا نشد."
        )
        blocks = [
            self.persona.to_prompt() if self.persona is not None else "",
            self.base_system_prompt,
            MEMORY_INSTRUCTIONS.format(memories=memories),
        ]
        return "\n\n".join(block for block in blocks if block)

    def _handle_command(self, text: str) -> str:
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) == 2 else ""

        if command == "/help":
            return HELP_TEXT
        if command == "/remember":
            if not argument:
                return "بعد از /remember متن خاطره را بنویس."
            memory_id = self.memory.add(argument)
            return f"ذخیره شد (شماره {memory_id})."
        if command == "/memories":
            items = self.memory.list_all()
            if not items:
                return "حافظه خالی است."
            return "\n".join(f"{item.id}: {item.text}" for item in items)
        if command == "/forget":
            if not argument.isdigit():
                return "شماره‌ی خاطره را بنویس، مثلاً: /forget 3"
            return (
                "حذف شد."
                if self.memory.delete(int(argument))
                else "چنین خاطره‌ای پیدا نشد."
            )
        if command == "/count":
            return f"تعداد خاطرات: {self.memory.count()}"
        if command == "/reset":
            self.reset()
            if self.session_store is not None:
                self.session_id = self.session_store.create_session()
            return "تاریخچه گفتگو پاک شد."
        return "دستور ناشناخته. /help را بزن."


import re as _re


def _parse_facts(result):
    """None = invalid format, [] = NO_FACT, otherwise only the valid FACT lines."""
    lines = [line.strip() for line in result.splitlines() if line.strip()]
    if lines == ["NO_FACT"]:
        return []
    facts = [line[5:].strip() for line in lines if line.startswith("FACT:")]
    facts = [fact for fact in facts if len(fact.split()) >= 2]
    return facts or None


def _looks_like_junk(text):
    t = text.strip()
    if len(t) > 300 or t.count("\n") >= 2:
        return True
    if t.endswith(("?", "؟")):
        return True
    return bool(_re.search(r"[=(){}\[\]_<>/\\]|\.py\b|\.txt\b|\bimport\b|\bdef\b|\bgit |\bpip |\$ ", t))


def _fact_is_grounded(fact, user_text):
    if _looks_like_junk(fact):
        return False
    if len(_re.findall(r"[\u0600-\u06FF]", fact)) < 5:
        return False
    def words(s):
        return set(_re.findall(r"[\u0600-\u06FF]{2,}", s.replace("\u200c", " ")))
    return len(words(fact) & words(user_text)) >= 2


def _is_smalltalk(text):
    words = _re.findall(r"[\u0600-\u06FFA-Za-z]+", text.replace("\u200c", " "))
    greet = {"سلام", "درود", "hi", "hello", "hey", "مرسی", "ممنون", "خداحافظ", "خوبی", "چطوری"}
    return 0 < len(words) <= 3 and any(w.lower() in greet for w in words)




def _wrap_extract(orig):
    def _extract(self, user_text):
        t = user_text.strip()
        if len(_re.findall(r"[\u0600-\u06FF]{2,}", t)) < 4 or _is_smalltalk(t):
            return
        return orig(self, user_text)
    return _extract


def _wrap_init(orig):
    def _init(self, *args, **kwargs):
        orig(self, *args, **kwargs)
        try:
            sp = self._build_system_prompt("\u0633\u0644\u0627\u0645")
            msgs = [{"role": "user", "content": "\u0633\u0644\u0627\u0645"}]
            for _ in self.provider.chat_stream(sp, msgs):
                break
        except Exception:
            pass
    return _init


ConversationEngine._extract_facts = _wrap_extract(ConversationEngine._extract_facts)
ConversationEngine.__init__ = _wrap_init(ConversationEngine.__init__)


def _wrap_web(orig):
    def _build(self, user_text):
        prompt = orig(self, user_text)
        try:
            from . import web
            extra = web.context_for(user_text)
        except Exception:
            extra = ""
        return prompt + "\n\n" + extra if extra else prompt
    return _build


ConversationEngine._build_system_prompt = _wrap_web(ConversationEngine._build_system_prompt)
