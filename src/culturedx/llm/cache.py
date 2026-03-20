# src/culturedx/llm/cache.py
"""SQLite-backed LLM response cache."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path


class LLMCache:
    """Cache LLM responses keyed by (provider, model, prompt_hash, language, input_hash)."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
        self._lock = threading.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "  provider TEXT, model TEXT, prompt_hash TEXT, language TEXT,"
            "  input_hash TEXT, response TEXT,"
            "  PRIMARY KEY (provider, model, prompt_hash, language, input_hash)"
            ")"
        )
        self._conn.commit()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._write_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @staticmethod
    def _hash_input(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(
        self, provider: str, model: str, prompt_hash: str, language: str, input_text: str
    ) -> str | None:
        input_hash = self._hash_input(input_text)
        with self._lock:
            row = self._conn.execute(
                "SELECT response FROM cache "
                "WHERE provider=? AND model=? AND prompt_hash=? AND language=? AND input_hash=?",
                (provider, model, prompt_hash, language, input_hash),
            ).fetchone()
        return row[0] if row else None

    def put(
        self,
        provider: str,
        model: str,
        prompt_hash: str,
        language: str,
        input_text: str,
        response: str,
    ) -> None:
        input_hash = self._hash_input(input_text)
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO cache "
                    "(provider, model, prompt_hash, language, input_hash, response) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (provider, model, prompt_hash, language, input_hash, response),
                )
                self._write_count += 1
                if self._write_count % 10 == 0:
                    self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Cache write failed (likely lock contention); LLM result still returned

    def flush(self) -> None:
        """Commit any pending writes."""
        with self._lock:
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.commit()
            self._conn.close()

    def __del__(self) -> None:
        try:
            self.flush()
        except Exception:
            pass
