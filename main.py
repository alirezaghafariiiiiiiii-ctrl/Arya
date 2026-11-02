"""Run ARIA Core in a terminal.

    python main.py
    ARIA_PROVIDER=ollama python main.py
    ARIA_MODEL=llama3.2 ARIA_DB=aria_memory.db python main.py
"""

from __future__ import annotations

import os

from arya_core.config import DB_PATH, MODEL_PATH, SESSION_DB
from arya_core.engine import ConversationEngine
from arya_core.memory import MemoryStore
from arya_core.providers import EchoProvider, LocalProvider, OllamaProvider, Provider
from arya_core.sessions import SessionStore

def build_provider() -> Provider:
    name = os.environ.get("ARIA_PROVIDER", "echo").lower()
    if name == "ollama":
        return OllamaProvider(model=os.environ.get("ARIA_MODEL", "llama3.2"))
    if name == "local":
        return LocalProvider(model_path=MODEL_PATH)
    return EchoProvider()


def main() -> None:
    with MemoryStore(DB_PATH) as memory, SessionStore(SESSION_DB) as sessions:
        session_id = sessions.get_latest_session() or sessions.create_session()
        engine = ConversationEngine(
            build_provider(),
            memory,
            session_store=sessions,
            session_id=session_id,
        )
        print("ARIA Core v2 آماده است. /help برای راهنما، Ctrl+C برای خروج.")
        try:
            while True:
                try:
                    text = input("\nتو: ")
                except EOFError:
                    break
                print(f"ARIA: {engine.generate_response(text)}")
        except KeyboardInterrupt:
            print("\nخداحافظ.")


if __name__ == "__main__":
    main()
