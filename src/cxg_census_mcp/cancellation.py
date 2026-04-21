"""Cooperative cancel token; use ``await checkpoint()`` in chunk loops."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field

from cxg_census_mcp.errors import CancelledError


@dataclass
class CancellationToken:
    _event: threading.Event = field(default_factory=threading.Event)
    reason: str | None = None

    def cancel(self, reason: str = "cancelled by client") -> None:
        self.reason = reason
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise CancelledError(self.reason or "cancelled")

    async def checkpoint(self) -> None:
        """Yield to the event loop and re-raise if cancelled.

        Use this between chunks of CPU-bound work so MCP's
        ``notifications/cancelled`` (which arrives as ``asyncio.CancelledError``
        on the request task) can be delivered without waiting for the loop
        to finish.
        """
        if self.cancelled:
            raise CancelledError(self.reason or "cancelled")
        await asyncio.sleep(0)

    async def wait(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._event.wait)


def linked_token(*tokens: CancellationToken) -> CancellationToken:
    """Return a token that fires when any source token fires."""
    out = CancellationToken()
    for t in tokens:
        if t.cancelled:
            out.cancel(t.reason or "cancelled")
            return out
        threading.Thread(
            target=lambda src=t, dst=out: (
                src._event.wait(),
                dst.cancel(src.reason or "cancelled"),
            ),
            daemon=True,
        ).start()
    return out
