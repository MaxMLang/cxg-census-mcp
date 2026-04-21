"""BLAKE2b over canonical JSON — ``call_id``, ``plan_hash``, etc."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(*parts: Any, length: int = 16) -> str:
    """Return a hex digest of canonicalised input. ``length`` is in hex chars."""
    h = hashlib.blake2b(digest_size=max(8, length // 2))
    for p in parts:
        h.update(b"\x00")
        h.update(canonical_json(p).encode("utf-8"))
    return h.hexdigest()[:length]
