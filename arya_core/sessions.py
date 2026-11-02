"""Persistent conversation sessions."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH


class SessionStore:
    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id);
            """
        )
        self._conn.commit()

    def create_session(self, session_id: str | None = None) -> str:
        sid = session_id or uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (sid, now, now),
        )
        self._conn.commit()
        return sid

    def get_latest_session(self) -> str | None:
        row = self._conn.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def has_session(self, session_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return row is not None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        if limit < 0:
            raise ValueError("limit cannot be negative")
        rows = self._conn.execute(
            """
            SELECT s.id, s.created_at, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count,
                   (SELECT content FROM messages m
                    WHERE m.session_id = s.id AND m.role = 'user'
                    ORDER BY m.id LIMIT 1) AS first_user_msg
            FROM sessions s
            ORDER BY s.updated_at DESC, s.rowid DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def add_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (session_id, "user", user_text, now),
                    (session_id, "assistant", assistant_text, now),
                ),
            )
            cursor = self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Unknown session: {session_id}")

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("Invalid message role")
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, now),
            )
            cursor = self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Unknown session: {session_id}")

    def get_messages(
        self, session_id: str, limit: int | None = None
    ) -> list[dict[str, str]]:
        if limit is not None and limit < 0:
            raise ValueError("limit cannot be negative")
        if limit is None:
            rows = self._conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ? ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        elif limit == 0:
            return []
        else:
            rows = self._conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ? ORDER BY id DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            rows = list(reversed(rows))
        return [dict(row) for row in rows]

    def count_messages(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["count"]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
