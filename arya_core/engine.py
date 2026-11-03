from arya_core.providers import ProviderError
from arya_core.persona import Persona
from arya_core.config import PERSONA_PATH
from arya_core.guard import conversation_only

NO_MODEL_MESSAGE = "مدل هوش مصنوعی در دسترس نیست."
BUILD_REFUSAL = "من فقط برای گفتگو اینجام؛ کد یا برنامه نمی‌نویسم."

try:
    _persona = Persona(PERSONA_PATH)
    _sys_prompt = _persona.to_prompt()
except Exception:
    _sys_prompt = "تو آریا هستی، یک دستیار فارسی‌زبان."

class ConversationEngine:
    def __init__(self, provider, memory=None, session_store=None, session_id=None):
        self.provider = provider
        self.memory = memory
        self.session_store = session_store
        self.session_id = session_id
        self.history = []
        self.base_system_prompt = _sys_prompt

    def _message(self, role, content):
        return {"role": role, "content": content}

    def handle_command(self, text):
        return "دستور ناشناخته."

    def _extract_facts(self, text):
        pass  # موقتاً غیرفعال تا خطای generator رخ ندهد

    def _build_system_prompt(self, text):
        return self.base_system_prompt

    def generate_response(self, user_text: str, stream: bool = False):
        text = user_text.strip()
        if not text:
            yield "پیام خالی است."
            return
            
        if text.startswith("/"):
            yield self.handle_command(text)
            return
            
        if self.provider is None:
            yield NO_MODEL_MESSAGE
            return

        if "کد" in text or "برنامه" in text or "تابع" in text or "عکس" in text or "تصویر" in text:
            yield BUILD_REFUSAL
            return

        user_message = self._message("user", text)
        self.history.append(user_message)

        try:
            self._extract_facts(text)
            reply_gen = self.provider.chat(
                self._build_system_prompt(text),
                self.history,
                stream=True
            )
        except Exception as error:
            yield f"خطا: {error}"
            return

        full_reply = ""
        for chunk in reply_gen:
            chunk_str = str(chunk)
            full_reply += chunk_str
            if stream:
                yield chunk_str

        if not stream:
            yield conversation_only(full_reply)
