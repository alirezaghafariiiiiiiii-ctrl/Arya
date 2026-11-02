import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

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
            print("⏳ در حال بارگذاری مدل حافظه معنایی (فقط بار اول کمی طول می‌کشد)...")
            self._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return self._model

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS core_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                conn.execute("ALTER TABLE core_memories ADD COLUMN embedding BLOB")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def add(self, text):
        if not text.strip(): return
        model = self._get_model()
        embedding = model.encode([text])[0]
        embedding_bytes = embedding.astype(np.float32).tobytes()

        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute("SELECT 1 FROM core_memories WHERE text = ?", (text,)).fetchone()
            if existing:
                return
            conn.execute("INSERT INTO core_memories (text, embedding) VALUES (?, ?)", (text, embedding_bytes))
            conn.commit()

    def search(self, query, top_k=3):
        model = self._get_model()
        query_embedding = model.encode([query])[0].reshape(1, -1)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, text, embedding FROM core_memories").fetchall()

        if not rows: return []

        texts = []
        embeddings = []
        for row in rows:
            if row["embedding"]: 
                texts.append(row["text"])
                embeddings.append(np.frombuffer(row["embedding"], dtype=np.float32))

        if not embeddings: return []

        embeddings_matrix = np.vstack(embeddings)
        similarities = cosine_similarity(query_embedding, embeddings_matrix)[0]
        top_indices = similarities.argsort()[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if similarities[idx] > 0.35:
                results.append(texts[idx])
        return results

    def list_all(self):
        class MemoryItem:
            def __init__(self, text): self.text = text
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT text FROM core_memories ORDER BY id").fetchall()
        return [MemoryItem(r[0]) for r in rows]

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
