"""Tiny sqlite-backed KV store with TTL + JSON serialization.

Replaces ``diskcache.Cache`` to avoid CVE-2025-69872 (pickle deserialization
of locally-writable cache values). All values are stored as JSON text, so a
tampered cache row at worst raises ``json.JSONDecodeError`` and the entry is
treated as a miss — there is no code-execution path on read.

Single-process, multi-thread safe (one shared connection, internal lock,
WAL journal). Not designed for cross-process sharing.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class SqliteKV:
    """Key/value store with per-entry expiry. Values are JSON-encoded."""

    def __init__(self, directory: str | Path, default_ttl: int) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "cache.sqlite"
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        # check_same_thread=False: we serialize access ourselves via _lock.
        # isolation_level=None keeps autocommit semantics so each statement
        # is its own transaction (matches the previous diskcache behavior).
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "  key TEXT PRIMARY KEY,"
            "  value TEXT NOT NULL,"
            "  expires_at REAL"
            ")"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS cache_expires_at_idx ON cache(expires_at)")

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            value_json, expires_at = row
            if expires_at is not None and expires_at < now:
                # Lazy eviction on read, mirroring diskcache.
                self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
        try:
            return json.loads(value_json)
        except json.JSONDecodeError:
            # Corrupted / tampered row: treat as miss and drop it.
            with self._lock:
                self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl_eff = self._default_ttl if ttl is None else ttl
        expires_at = time.time() + ttl_eff if ttl_eff > 0 else None
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, payload, expires_at),
            )

    def delete(self, key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache")

    def expire(self) -> int:
        """Drop all expired rows. Returns the number reclaimed."""
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            return cur.rowcount or 0

    def __len__(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()
