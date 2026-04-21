"""Unit tests for ProgressReporter throttling and CancellationToken checkpoint."""

from __future__ import annotations

import asyncio

import pytest

from cxg_census_mcp.cancellation import CancellationToken
from cxg_census_mcp.errors import CancelledError
from cxg_census_mcp.progress import ProgressReporter, maybe_report

pytestmark = pytest.mark.asyncio


async def test_progress_reporter_throttles_to_min_interval():
    events: list[tuple[float, str | None]] = []

    async def cb(fraction: float, message: str | None) -> None:
        events.append((fraction, message))

    reporter = ProgressReporter(cb=cb, total=100, min_interval_ms=200)
    for i in range(10):
        await reporter.update(i, f"step {i}")
    await reporter.update(100, "done")
    assert len(events) <= 3
    assert events[-1][0] == 1.0


async def test_progress_reporter_no_op_when_no_callback():
    reporter = ProgressReporter(cb=None, total=10)
    await reporter.update(5, "halfway")  # must not raise


async def test_maybe_report_emits_completion_even_without_updates():
    events: list[tuple[float, str | None]] = []

    async def cb(fraction: float, message: str | None) -> None:
        events.append((fraction, message))

    async with maybe_report(cb=cb, total=10):
        pass

    assert events == [(1.0, "complete")]


async def test_maybe_report_callback_exceptions_do_not_propagate():
    async def cb(fraction: float, message: str | None) -> None:
        raise RuntimeError("client disconnected")

    async with maybe_report(cb=cb, total=1):
        pass


async def test_cancellation_token_checkpoint_raises_after_cancel():
    token = CancellationToken()
    await token.checkpoint()  # ok before cancel
    token.cancel("user pressed stop")
    with pytest.raises(CancelledError):
        await token.checkpoint()


async def test_cancellation_token_yield_lets_other_task_observe_cancel():
    token = CancellationToken()
    observed: list[bool] = []

    async def watcher() -> None:
        await asyncio.sleep(0.01)
        token.cancel("stop")

    async def worker() -> None:
        for _ in range(100):
            await token.checkpoint()
            await asyncio.sleep(0.001)
        observed.append(False)

    with pytest.raises(CancelledError):
        await asyncio.gather(watcher(), worker())
    assert observed == []
