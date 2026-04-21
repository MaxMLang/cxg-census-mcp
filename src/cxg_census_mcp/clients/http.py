"""Shared async HTTP client with token bucket, retry, and circuit breaker."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache

import httpx

from cxg_census_mcp import __version__
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import OntologyUnavailableError
from cxg_census_mcp.logging_setup import get_logger

log = get_logger(__name__)

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
DEFAULT_RETRIES = 4


@dataclass
class TokenBucket:
    """Simple per-minute token bucket."""

    capacity: int
    _events: deque[float] = field(default_factory=deque)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - 60.0
            while self._events and self._events[0] < cutoff:
                self._events.popleft()
            if len(self._events) >= self.capacity:
                wait = max(0.0, 60.0 - (now - self._events[0]))
                await asyncio.sleep(wait)
                now = time.monotonic()
                while self._events and self._events[0] < (now - 60.0):
                    self._events.popleft()
            self._events.append(time.monotonic())


@dataclass
class CircuitBreaker:
    """Trips after `fail_threshold` consecutive failures, half-open after cooldown."""

    fail_threshold: int = 5
    cooldown_s: float = 30.0
    _consecutive_fails: int = 0
    _opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        # Half-open after cooldown elapses.
        return (time.monotonic() - self._opened_at) < self.cooldown_s

    def record_success(self) -> None:
        self._consecutive_fails = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_fails += 1
        if self._consecutive_fails >= self.fail_threshold:
            self._opened_at = time.monotonic()


class HTTPClient:
    """Wraps :class:`httpx.AsyncClient` with rate limiting, retries, and a breaker."""

    def __init__(
        self,
        *,
        max_per_minute: int,
        circuit_threshold: int,
        connect_timeout: float = 30.0,
        read_timeout: float = 60.0,
    ) -> None:
        self._bucket = TokenBucket(capacity=max_per_minute)
        self._breaker = CircuitBreaker(fail_threshold=circuit_threshold)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=connect_timeout, read=read_timeout, write=30.0, pool=30.0
            ),
            headers={"User-Agent": f"cxg-census-mcp/{__version__}"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(self, url: str, *, params: dict | None = None) -> dict:
        if self._breaker.is_open:
            raise OntologyUnavailableError(
                "OLS circuit breaker is open after repeated failures.",
            )
        await self._bucket.acquire()

        for attempt in range(DEFAULT_RETRIES):
            try:
                resp = await self._client.get(url, params=params)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
                self._breaker.record_failure()
                if attempt == DEFAULT_RETRIES - 1:
                    raise OntologyUnavailableError(f"OLS unreachable: {exc}") from exc
                await asyncio.sleep(_backoff(attempt))
                continue

            if resp.status_code in RETRY_STATUS:
                self._breaker.record_failure()
                if attempt == DEFAULT_RETRIES - 1:
                    raise OntologyUnavailableError(f"OLS returned {resp.status_code} after retries")
                wait = _retry_after(resp) or _backoff(attempt)
                log.warning(
                    "ols_retry", url=url, status=resp.status_code, attempt=attempt, wait_s=wait
                )
                await asyncio.sleep(wait)
                continue

            if resp.status_code >= 400:
                self._breaker.record_failure()
                raise OntologyUnavailableError(
                    f"OLS error {resp.status_code} for {url}: {resp.text[:200]}"
                )

            self._breaker.record_success()
            return resp.json()

        raise OntologyUnavailableError("OLS retry loop exhausted unexpectedly")


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _backoff(attempt: int) -> float:
    return min(30.0, (2.0**attempt) * 0.5)


@lru_cache(maxsize=1)
def get_http_client() -> HTTPClient:
    s = get_settings()
    return HTTPClient(
        max_per_minute=s.max_http_per_minute,
        circuit_threshold=s.ols_circuit_breaker_fails,
    )
