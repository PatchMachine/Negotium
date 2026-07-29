"""Sliding-window limiter: window expiry, multi-key denial, clear-on-success."""

from __future__ import annotations

from negotium.app.services.rate_limit import SlidingWindowLimiter, client_ip


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_until_max_failures_then_denies() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_failures=3, window_seconds=60.0, clock=clock)

    for _ in range(2):
        assert limiter.check("k").allowed
        limiter.record_failure("k")
    assert limiter.check("k").allowed
    limiter.record_failure("k")

    decision = limiter.check("k")
    assert not decision.allowed
    assert decision.retry_after_seconds > 0


def test_window_expiry_frees_the_key() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_failures=2, window_seconds=60.0, clock=clock)
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert not limiter.check("k").allowed

    clock.now += 61.0
    assert limiter.check("k").allowed


def test_any_key_over_limit_denies() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_failures=1, window_seconds=60.0, clock=clock)
    limiter.record_failure("ip:1.2.3.4")

    decision = limiter.check("user:alice", "ip:1.2.3.4")
    assert not decision.allowed


def test_retry_after_counts_down_with_the_oldest_mark() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_failures=1, window_seconds=60.0, clock=clock)
    limiter.record_failure("k")

    clock.now += 20.0
    decision = limiter.check("k")
    assert not decision.allowed
    assert decision.retry_after_seconds == 41  # 60 - 20, rounded up


def test_clear_resets_the_counter() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_failures=1, window_seconds=60.0, clock=clock)
    limiter.record_failure("k")
    assert not limiter.check("k").allowed

    limiter.clear("k")
    assert limiter.check("k").allowed


def test_client_ip_falls_back_to_unknown() -> None:
    assert client_ip("10.0.0.1") == "10.0.0.1"
    assert client_ip(None) == "unknown"
    assert client_ip("") == "unknown"
