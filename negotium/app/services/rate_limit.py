"""In-memory sliding-window limiter for credential endpoints.

State is process-local by design: the documented deployment is a single
uvicorn process, failure windows are short-lived, and file-backing would add
a locked archive write to every failed login attempt. A multi-worker
deployment needs a shared (file- or store-backed) implementation instead.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class SlidingWindowLimiter:
    """Denies once any key accumulates ``max_failures`` marks in the window."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._clock = clock
        self._marks: dict[str, list[float]] = {}

    def check(self, *keys: str) -> RateLimitDecision:
        now = self._clock()
        retry_after = 0
        for key in keys:
            timestamps = self._prune(key, now)
            if len(timestamps) >= self._max_failures:
                remaining = int(timestamps[0] + self._window_seconds - now) + 1
                retry_after = max(retry_after, remaining)
        if retry_after:
            return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
        return RateLimitDecision(allowed=True)

    def record_failure(self, *keys: str) -> None:
        now = self._clock()
        for key in keys:
            timestamps = self._prune(key, now)
            timestamps.append(now)
            self._marks[key] = timestamps

    def clear(self, *keys: str) -> None:
        for key in keys:
            self._marks.pop(key, None)

    def _prune(self, key: str, now: float) -> list[float]:
        timestamps = [
            stamp for stamp in self._marks.get(key, []) if now - stamp < self._window_seconds
        ]
        if timestamps:
            self._marks[key] = timestamps
        else:
            self._marks.pop(key, None)
        return timestamps


def client_ip(client_host: str | None) -> str:
    return client_host or "unknown"
