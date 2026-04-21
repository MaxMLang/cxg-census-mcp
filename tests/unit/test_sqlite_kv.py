"""Smoke tests for the sqlite+json KV store that replaced diskcache."""

from __future__ import annotations

import time
from pathlib import Path

from cxg_census_mcp.caches._sqlite_kv import SqliteKV


def _kv(tmp_path: Path, ttl: int = 60) -> SqliteKV:
    return SqliteKV(tmp_path / "kv", default_ttl=ttl)


def test_round_trip_json_serializable_value(tmp_path: Path) -> None:
    kv = _kv(tmp_path)
    payload = {"a": 1, "b": ["x", "y"], "c": None}
    kv.set("k", payload)
    assert kv.get("k") == payload


def test_missing_key_returns_none(tmp_path: Path) -> None:
    assert _kv(tmp_path).get("never-set") is None


def test_overwrite_replaces_value(tmp_path: Path) -> None:
    kv = _kv(tmp_path)
    kv.set("k", "first")
    kv.set("k", "second")
    assert kv.get("k") == "second"


def test_ttl_expiry_is_lazy_on_read(tmp_path: Path) -> None:
    kv = _kv(tmp_path, ttl=60)
    kv.set("k", "v", ttl=0)  # ttl<=0 means no expiry
    assert kv.get("k") == "v"

    kv.set("short", "v", ttl=1)
    # Force the row to be considered expired by walking the clock past it.
    time.sleep(1.05)
    assert kv.get("short") is None


def test_explicit_expire_drops_expired_rows(tmp_path: Path) -> None:
    kv = _kv(tmp_path, ttl=60)
    kv.set("a", 1, ttl=1)
    kv.set("b", 2)  # default ttl=60s, should survive
    time.sleep(1.05)
    reclaimed = kv.expire()
    assert reclaimed == 1
    assert kv.get("a") is None
    assert kv.get("b") == 2


def test_clear_drops_everything(tmp_path: Path) -> None:
    kv = _kv(tmp_path)
    kv.set("a", 1)
    kv.set("b", 2)
    assert len(kv) == 2
    kv.clear()
    assert len(kv) == 0
    assert kv.get("a") is None


def test_corrupted_row_treated_as_miss_not_crash(tmp_path: Path) -> None:
    """Tampered row -> JSONDecodeError -> miss + drop. No code-execution path."""
    kv = _kv(tmp_path)
    kv.set("k", "fine")
    # Stomp the value column with garbage that is not valid JSON. A pickle
    # backend would happily try to deserialize this; we expect a clean miss.
    with kv._lock:
        kv._conn.execute("UPDATE cache SET value = ? WHERE key = ?", ("not-json{", "k"))
    assert kv.get("k") is None
    # Corrupted row should also be evicted.
    assert len(kv) == 0


def test_persists_across_reopen(tmp_path: Path) -> None:
    kv1 = _kv(tmp_path)
    kv1.set("k", {"v": 1})
    kv1.close()

    kv2 = SqliteKV(tmp_path / "kv", default_ttl=60)
    assert kv2.get("k") == {"v": 1}


def test_unicode_round_trip(tmp_path: Path) -> None:
    kv = _kv(tmp_path)
    kv.set("k", {"label": "髓样树突状细胞 — αβ"})
    assert kv.get("k") == {"label": "髓样树突状细胞 — αβ"}
