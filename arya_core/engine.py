from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence

from .memory import MemoryStore
from .providers import Provider, ProviderError
from .sessions import SessionStore

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "تو آریا هستی، یک دستیار فارسی‌زبان با حافظه‌ی پایدار. "
    "کوتاه، دقیق و به زبان کاربر پاسخ بده."
)

MEMORY_INSTRUCTIONS = """از اطلاعات زیر برای پاسخ به کاربر استفاده کن.
این‌ها دانسته‌های ذخیره‌شده درباره‌ی کاربر هستند، نه نقل‌قولی از پیام‌های قبلی.
ضمیر «من» در خاطره‌ها به کاربر اشاره دارد، نه به تو. وقتی کاربر می‌پرسد «اسم من چیه؟» و خاطره می‌گوید «اسم من رضاست»، پاسخ بده «اسمت رضاست.»
معنای جمله‌ها و علاقه‌ها را استنباط کن؛ مثلاً «عاشق غذای مادرم هستم» یعنی کاربر غذای مادرش را دوست دارد.
اگر پرسیده شد «من از چه غذایی خوشم میاد؟» و این دانسته موجود بود، مستقیم بگو «از غذای مادرت خوشت می‌آید؛ نوع غذا مشخص نشده.» درباره‌ی کاربر با «تو» حرف بزن، نه با «من». در پاسخ به اطلاعات صریح، از «شاید» و «احتمالاً» استفاده نکن.
جزئیات ناموجود را نساز. فقط اگر هیچ اطلاعات مرتبطی نیست بگو نمی‌دانی.
اطلاعات:
{memories}"""

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
        self.base_system_prompt = (
            personality.strip() if personality is not None else system_prompt.strip()
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

        assistant_message = self._message("assistant", reply)
        if self.session_store is not None and self.session_id is not None:
            self.session_store.add_message(
                self.session_id, "assistant", reply.strip()
            )
        self.history.append(assistant_message)
        return reply.strip()

    def _extract_facts(self, user_text: str) -> None:
        if hasattr(self.provider, "chat"):
            result = self.provider.chat(
                FACT_EXTRACTION_PROMPT,
                [{"role": "user", "content": user_text}],
            )
        else:
            result = self.provider.generate(
                (
                    self._message("system", FACT_EXTRACTION_PROMPT),
                    self._message("user", user_text),
                )
            )

        lines = [line.strip() for line in result.splitlines() if line.strip()]
        if lines == ["NO_FACT"]:
            return
        facts = [line.removeprefix("FACT:").strip() for line in lines]
        if not lines or any(
            not line.startswith("FACT:") or len(fact.split()) < 2
            for line, fact in zip(lines, facts)
        ):
            logger.warning("Fact extraction returned an invalid format; no facts saved")
            return

        for fact in facts:
            self.memory.add(fact)

    def _build_system_prompt(self, user_text: str) -> str:
        recalled = self.memory.search(user_text, limit=self.max_recalled)
        block = (
            "\n".join(f"- {item.text}" for item in recalled)
            if recalled
            else "دانسته‌ی مرتبطی درباره‌ی این سؤال پیدا نشد."
        )
        return f"{self.base_system_prompt}\n\n{MEMORY_INSTRUCTIONS.format(memories=block)}"

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
