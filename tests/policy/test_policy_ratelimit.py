"""Sliding-window rate limiter."""

from __future__ import annotations

import threading

import pytest

from mirsad.policy import RateLimiter


def test_hit_counts_calls_inside_the_window():
    rl = RateLimiter()
    assert [rl.hit("k", 10, t) for t in (0, 1, 2)] == [1, 2, 3]


def test_window_slides_and_old_calls_expire():
    rl = RateLimiter()
    for t in (0, 1, 2):
        rl.hit("k", 10, t)
    assert rl.peek("k", 10, 9.5) == 3
    assert rl.peek("k", 10, 10.0) == 2  # the call at t=0 is exactly one window old -> outside
    assert rl.hit("k", 10, 11.5) == 2   # t=0 and t=1 expired; t=2 and this call remain
    assert rl.hit("k", 10, 100) == 1


def test_peek_does_not_record():
    rl = RateLimiter()
    assert rl.peek("k", 60, 0) == 0
    rl.hit("k", 60, 0)
    assert rl.peek("k", 60, 1) == 1
    assert rl.peek("k", 60, 1) == 1
    assert rl.hit("k", 60, 2) == 2


def test_keys_are_independent():
    rl = RateLimiter()
    rl.hit("a", 60, 0)
    rl.hit("a", 60, 1)
    assert rl.hit("b", 60, 1) == 1
    assert len(rl) == 2


def test_reset_all_and_by_prefix():
    rl = RateLimiter()
    rl.hit("rl:agent=a;tool=x", 60, 0)
    rl.hit("rl:agent=b;tool=x", 60, 0)
    rl.reset("rl:agent=a")
    assert rl.peek("rl:agent=a;tool=x", 60, 1) == 0
    assert rl.peek("rl:agent=b;tool=x", 60, 1) == 1
    rl.reset()
    assert len(rl) == 0


def test_entries_per_key_are_bounded():
    rl = RateLimiter(max_entries_per_key=5)
    counts = [rl.hit("k", 1000, t) for t in range(20)]
    assert counts[-1] == 5  # saturates at the bound instead of growing without limit


def test_number_of_keys_is_bounded_by_evicting_idle_keys():
    rl = RateLimiter(max_keys=3)
    for i in range(3):
        rl.hit(f"old{i}", 10, 0)
    rl.hit("new", 10, 100)  # all old keys are idle at t=100
    assert len(rl) == 1


def test_eviction_drops_the_stalest_key_when_none_is_idle():
    rl = RateLimiter(max_keys=2)
    rl.hit("a", 1000, 0)
    rl.hit("b", 1000, 5)
    rl.hit("c", 1000, 6)
    assert len(rl) == 2
    assert rl.peek("a", 1000, 7) == 0 and rl.peek("b", 1000, 7) == 1


def test_invalid_bounds_are_rejected():
    with pytest.raises(ValueError):
        RateLimiter(max_entries_per_key=0)


def test_concurrent_hits_are_all_counted():
    rl = RateLimiter()
    threads = [threading.Thread(target=lambda: [rl.hit("k", 3600, 1.0) for _ in range(250)]) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert rl.peek("k", 3600, 1.0) == 2000
