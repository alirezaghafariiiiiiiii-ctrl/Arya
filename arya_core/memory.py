import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

from .config import DB_PATH


_DIGITS = {ord(char): str(value) for value, char in enumerate("۰۱۲۳۴۵۶۷۸۹")}
_DIGITS.update({ord(char): str(value) for value, char in enumerate("٠١٢٣٤٥٦٧٨٩")})
_LETTERS = {ord("ي"): "ی", ord("ى"): "ی", ord("ك"): "ک", ord("ة"): "ه"}
_TABLE = {**_DIGITS, **_LETTERS}
_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670\u0640]")
_WORD = re.compile(r"\w+", re.UNICODE)

STOPWORDS = {
    "من", "ما", "تو", "شما", "او", "این", "آن", "که", "را", "رو", "و", "در",
    "به", "از", "با", "برای", "چی", "چیه", "چه", "چیست", "کی", "کجا", "هست",
    "هستم", "است", "بود", "یه", "یک", "هم", "اما", "اگر", "آیا", "بگو",
    "لطفا", "تا", "بر", "می", "ها", "های",
    "the", "a", "an", "is", "are", "what", "my", "of", "to", "and", "in",
    "do", "i", "me", "you", "it", "who", "where", "when",
}


def normalize(text: str) -> str:
    text = text.translate(_TABLE)
    text = _DIACRITICS.sub("", text)
    text = text.replace("\u200c", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in _WORD.findall(normalize(text)):
        if len(word) >= 2 and word not in STOPWORDS and word not in tokens:
            tokens.append(word)
    return tokens


@dataclass(frozen=True)
class Memory:
    id: int
    text: str
    created_at: float


class AryaMemory:
    def __init__(self, database_path: str | Path = DB_PATH):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 3,
                created_at TEXT NOT NULL
            )""")

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def add_memory(self, content, category="general", importance=3):
        with self.connect() as db:
            cur = db.execute(
                "INSERT INTO memories (category,content,importance,created_at) VALUES (?,?,?,?)",
                (category, content, importance, datetime.now(timezone.utc).isoformat())
            )
            return cur.lastrowid

    def search(self, query, limit=10):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM memories WHERE content LIKE ? OR category LIKE ? ORDER BY importance DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM memories ORDER BY id DESC")]

    def delete_memory(self, memory_id):
        with self.connect() as db:
            return db.execute("DELETE FROM memories WHERE id=?", (memory_id,)).rowcount > 0

    def count(self):
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]


class MemoryStore:
    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS core_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                norm TEXT NOT NULL,
                created_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    def add(self, text: str) -> int:
        text = text.strip()
        if not text:
            raise ValueError("متن خاطره خالی است")

        norm = normalize(text)
        row = self._conn.execute(
            "SELECT id FROM core_memories WHERE norm = ?", (norm,)
        ).fetchone()
        if row:
            return row[0]

        cur = self._conn.execute(
            "INSERT INTO core_memories (text, norm, created_at) VALUES (?, ?, ?)",
            (text, norm, time.time()),
        )
        self._conn.commit()
        if cur.lastrowid is None:
            raise RuntimeError("SQLite did not return an ID for the new memory")
        return cur.lastrowid

    def delete(self, memory_id: int) -> bool:
        cur = self._conn.execute(
            "DELETE FROM core_memories WHERE id = ?", (memory_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        tokens = tokenize(query)
        if not tokens:
            return []

        matches = []
        parameters: list[str] = []
        for token in tokens:
            alternatives = [token]
            if token.endswith("ی") and len(token) > 4:
                alternatives.append(token[:-1])
            matches.append(
                f"CASE WHEN ({' OR '.join('instr(norm, ?) > 0' for _ in alternatives)}) "
                "THEN 1 ELSE 0 END"
            )
            parameters.extend(alternatives)
        score = " + ".join(matches)
        rows = self._conn.execute(
            f"""SELECT id, text, created_at FROM (
                SELECT id, text, created_at, ({score}) AS score
                FROM core_memories
            ) WHERE score > 0
            ORDER BY score DESC, created_at DESC LIMIT ?""",
            (*parameters, limit),
        ).fetchall()
        return [Memory(*row) for row in rows]

    def list_all(self) -> list[Memory]:
        rows = self._conn.execute(
            "SELECT id, text, created_at FROM core_memories ORDER BY id"
        ).fetchall()
        return [Memory(*row) for row in rows]

    def count(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM core_memories"
        ).fetchone()[0]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
