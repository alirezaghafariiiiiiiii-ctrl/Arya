import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("ARIA_DB", DATA_DIR / "arya_memory.sqlite3"))
SESSION_DB = Path(
    os.getenv("ARIA_SESSION_DB", DATA_DIR / "arya_sessions.sqlite3")
)
MODEL_PATH = Path(
    os.getenv(
        "ARIA_MODEL_PATH",
        MODELS_DIR / "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
    )
)
PERSONA_PATH = Path(os.getenv("ARIA_PERSONA", Path(__file__).parent / "persona.yaml"))
