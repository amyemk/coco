"""
AI Response Cache Manager

SQLite-backed cache for Claude API responses.
Avoids redundant API calls for identical prompts within the TTL window.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


class CacheManager:
    """
    SQLite-backed prompt/response cache.

    Keys are SHA-256 hashes of (model, prompt). Values are response strings.
    Entries expire after cache_ttl_hours.
    """

    def __init__(self, db_path: str, cache_ttl_hours: int = 24):
        self.cache_ttl_hours = cache_ttl_hours
        self._conn = self._init_db(db_path)

    def _init_db(self, db_path: str) -> sqlite3.Connection:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_response_cache (
                cache_key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_expires ON ai_response_cache(expires_at)"
        )
        conn.commit()
        return conn

    def _make_key(self, model: str, prompt: str, system: Optional[str]) -> str:
        payload = json.dumps({"model": model, "prompt": prompt, "system": system or ""})
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, model: str, prompt: str, system: Optional[str] = None) -> Optional[str]:
        key = self._make_key(model, prompt, system)
        now = datetime.utcnow().isoformat()
        row = self._conn.execute(
            "SELECT response FROM ai_response_cache WHERE cache_key = ? AND expires_at > ?",
            (key, now),
        ).fetchone()
        if row:
            logger.debug("ai_cache_hit", key=key[:12])
            return row[0]
        return None

    def set(self, model: str, prompt: str, response: str, system: Optional[str] = None) -> None:
        key = self._make_key(model, prompt, system)
        now = datetime.utcnow()
        expires = (now + timedelta(hours=self.cache_ttl_hours)).isoformat()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO ai_response_cache
                (cache_key, response, model, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, response, model, now.isoformat(), expires),
        )
        self._conn.commit()
        logger.debug("ai_cache_set", key=key[:12], expires=expires)

    def purge_expired(self) -> int:
        now = datetime.utcnow().isoformat()
        cursor = self._conn.execute(
            "DELETE FROM ai_response_cache WHERE expires_at <= ?", (now,)
        )
        self._conn.commit()
        count = cursor.rowcount
        if count:
            logger.info("ai_cache_purged", expired_entries=count)
        return count
