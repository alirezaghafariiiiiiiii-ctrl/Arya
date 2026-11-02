import os
import threading

import gradio as gr

from arya_core.config import DB_PATH, MODEL_PATH, SESSION_DB
from arya_core.engine import ConversationEngine
from arya_core.memory import MemoryStore
from arya_core.providers import LocalProvider, OllamaProvider
from arya_core.sessions import SessionStore

OWNER_USER = os.environ.get("ARYA_OWNER_USER", "")
OWNER_PASSWORD = os.environ.get("ARYA_OWNER_PASSWORD", "")


def build_provider():
    name = os.environ.get("ARIA_PROVIDER", "local").lower()
    if name == "ollama":
        return OllamaProvider(model=os.environ.get("ARIA_MODEL", "llama3.2"))
    return LocalProvider(model_path=MODEL_PATH)


_lock = threading.Lock()
_memory = MemoryStore(DB_PATH)
_sessions = SessionStore(SESSION_DB)
_session_id = _sessions.get_latest_session() or _sessions.create_session()
_engine = ConversationEngine(
    build_provider(),
    _memory,
    session_store=_sessions,
    session_id=_session_id,
)


def chat(message, history):
    if not isinstance(message, str) or not message.strip():
        return "لطفاً یک پیام بنویس."
    try:
        with _lock:
            return _engine.generate_response(message)
    except Exception as error:
        print(f"Arya error: {error}")
        return "مشکلی پیش آمد. دوباره تلاش کن."


configured = bool(OWNER_USER and OWNER_PASSWORD)

if configured:
    demo = gr.ChatInterface(
        fn=chat,
        type="messages",
        title="آریا | گفتگو",
        description="فقط گفتگو",
    )
else:
    demo = gr.Interface(
        fn=lambda m: "ابتدا ARYA_OWNER_USER و ARYA_OWNER_PASSWORD را تنظیم کن.",
        inputs=gr.Textbox(label="پیام"),
        outputs=gr.Textbox(label="پاسخ"),
        title="Arya - Setup Required",
    )

demo.queue()
demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 10000)),
    auth=(OWNER_USER, OWNER_PASSWORD) if configured else None,
)
