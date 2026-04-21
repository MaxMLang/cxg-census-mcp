"""One open SOMA handle per Census version per process."""

from __future__ import annotations

import threading
from typing import Any


class _HandlePool:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handles: dict[str, Any] = {}

    def get(self, version: str) -> Any:
        with self._lock:
            return self._handles.get(version)

    def put(self, version: str, handle: Any) -> Any:
        with self._lock:
            existing = self._handles.get(version)
            if existing is not None:
                return existing
            self._handles[version] = handle
            return handle

    def close_all(self) -> None:
        import contextlib

        with self._lock:
            for h in self._handles.values():
                close = getattr(h, "close", None)
                if callable(close):
                    with contextlib.suppress(Exception):
                        close()
            self._handles.clear()

    def known(self) -> list[str]:
        with self._lock:
            return list(self._handles)


_pool = _HandlePool()


def get_handle_pool() -> _HandlePool:
    return _pool
