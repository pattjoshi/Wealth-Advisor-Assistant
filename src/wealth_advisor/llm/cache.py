from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from wealth_advisor.llm.base import LLMResponse


class LLMCache:
    """SQLite-backed cache keyed by a hash of (model, findings). A second run with
    identical findings is a cache hit — zero tokens, zero cost, no network call."""

    def __init__(self, db_path: Path | str) -> None:
        if isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                model TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def make_key(model: str, findings_payload: Any) -> str:
        serialized = json.dumps(findings_payload, sort_keys=True, default=str)
        return hashlib.sha256(f"{model}:{serialized}".encode()).hexdigest()

    def get(self, cache_key: str) -> LLMResponse | None:
        row = self._conn.execute(
            "SELECT text, input_tokens, output_tokens, model FROM llm_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        text, input_tokens, output_tokens, model = row
        return LLMResponse(
            text=text, input_tokens=input_tokens, output_tokens=output_tokens, model=model
        )

    def set(self, cache_key: str, response: LLMResponse) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache
                (cache_key, text, input_tokens, output_tokens, model)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                response.text,
                response.input_tokens,
                response.output_tokens,
                response.model,
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
