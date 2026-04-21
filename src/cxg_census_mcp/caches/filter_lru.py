"""In-memory LRU of recent plans (hot path for export_snippet)."""

from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from typing import Any

from cxg_census_mcp.config import get_settings


class FilterLRU:
    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._data: OrderedDict[str, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any:
        if key in self._data:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


@lru_cache(maxsize=1)
def get_filter_lru() -> FilterLRU:
    return FilterLRU(capacity=get_settings().last_call_lru_size)
