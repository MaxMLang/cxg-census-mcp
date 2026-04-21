"""Throttled MCP progress callbacks (no-op when no handler)."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field

from cxg_census_mcp.config import get_settings

ProgressCallback = Callable[[float, str | None], Awaitable[None]]


@dataclass
class ProgressReporter:
    """Calls ``cb(fraction, message)``; throttled by ``min_interval_ms``."""

    cb: ProgressCallback | None = None
    total: int = 1
    min_interval_ms: int = 250
    _last_emit_ms: float = field(default=0.0)
    _started_ms: float = field(default_factory=lambda: time.monotonic() * 1000)

    async def update(self, current: int, message: str | None = None) -> None:
        if self.cb is None:
            return
        now_ms = time.monotonic() * 1000
        if (now_ms - self._last_emit_ms) < self.min_interval_ms and current < self.total:
            return
        self._last_emit_ms = now_ms
        fraction = 0.0 if self.total == 0 else min(1.0, current / self.total)
        await self.cb(fraction, message)

    @property
    def elapsed_ms(self) -> float:
        return time.monotonic() * 1000 - self._started_ms


@asynccontextmanager
async def maybe_report(cb: ProgressCallback | None, total: int = 1):
    """Context manager that yields a ``ProgressReporter``.

    Reports a final 1.0 update on clean exit, even for zero-length work, so
    clients see a deterministic completion event.
    """
    reporter = ProgressReporter(cb=cb, total=total)
    try:
        yield reporter
    finally:
        if cb is not None:
            with suppress(Exception):
                await cb(1.0, "complete")


def should_report(estimated_runtime_ms: int | None) -> bool:
    """Decide whether progress reporting should be wired up for a planned job."""
    if estimated_runtime_ms is None:
        return False
    return estimated_runtime_ms >= get_settings().progress_min_ms
