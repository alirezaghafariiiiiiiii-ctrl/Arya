import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class MemoryItem:
    def __init__(self, text, id=None):
        self.text = text
        self.id = id

class MemoryStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self._model = None
        self._init_db()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _get_model(self):
        if self._model is None:
            print("⏳ لود مدل حافظه معنایی...")
            self._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return self._model

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS core_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    embedding BLOB
                )
            """)
            conn.commit()

    def add(self, text):
        if not text.strip(): return
        model = self._get_model()
        embedding = model.encode([text])[0]
        embedding_bytes = embedding.astype(np.float32).tobytes()

        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute("SELECT 1 FROM core_memories WHERE text = ?", (text,)).fetchone()
            if not existing:
                conn.execute("INSERT INTO core_memories (text, embedding) VALUES (?, ?)", (text, embedding_bytes))
                conn.commit()

    def search(self, query, top_k=3, limit=None):
        if limit is not None:
            top_k = limit
        model = self._get_model()
        query_embedding = model.encode([query])[0].reshape(1, -1)

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT text, embedding FROM core_memories").fetchall()

        if not rows: return []

        texts, embeddings = [], []
        for text, emb in rows:
            if emb:
                texts.append(text)
                embeddings.append(np.frombuffer(emb, dtype=np.float32))

        if not embeddings: return []

        similarities = cosine_similarity(query_embedding, np.vstack(embeddings))[0]
        top_indices = similarities.argsort()[-top_k:][::-1]

        return [MemoryItem(texts[idx]) for idx in top_indices if similarities[idx] > 0.35]

    def list_all(self):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT text FROM core_memories ORDER BY id").fetchall()
        return [MemoryItem(r[0], r[1]) for r in rows]

    def count(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM core_memories").fetchone()[0]

    def delete(self, index):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM core_memories WHERE id = ?", (index,))
            conn.commit()

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM core_memories")
            conn.commit()

    def close(self):
        pass
