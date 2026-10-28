"""In-memory sliding-window rate limiter (one deque of timestamps per key)."""

from __future__ import annotations

import threading
from collections import deque


class RateLimiter:
    """Thread-safe sliding-window counter.

    ``hit`` records a call and returns how many calls fall inside the window
    ``(now - per_seconds, now]`` including this one. ``peek`` counts without
    recording. Each key keeps at most ``max_entries_per_key`` timestamps, which
    bounds memory when a misbehaving agent hammers a tool. Counts saturate at
    that value, so keep it above every ``max_calls`` in the policy.
    """

    def __init__(self, *, max_entries_per_key: int = 10_000, max_keys: int = 100_000) -> None:
        if max_entries_per_key < 1 or max_keys < 1:
            raise ValueError("max_entries_per_key and max_keys must be positive")
        self._max_entries = max_entries_per_key
        self._max_keys = max_keys
        self._windows: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, per_seconds: float, now: float) -> int:
        """Record a call at ``now``; return the number of calls in the window including this one."""
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                if len(self._windows) >= self._max_keys:
                    self._evict_idle(now, per_seconds)
                window = deque(maxlen=self._max_entries)
                self._windows[key] = window
            self._prune(window, per_seconds, now)
            window.append(now)
            return len(window)

    def peek(self, key: str, per_seconds: float, now: float) -> int:
        """Number of calls in the window ending at ``now``, without recording anything."""
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                return 0
            cutoff = now - per_seconds
            return sum(1 for ts in window if cutoff < ts <= now)

    def reset(self, prefix: str | None = None) -> None:
        """Forget all counters, or only those whose key starts with ``prefix``."""
        with self._lock:
            if prefix is None:
                self._windows.clear()
            else:
                for key in [k for k in self._windows if k.startswith(prefix)]:
                    del self._windows[key]

    def __len__(self) -> int:
        with self._lock:
            return len(self._windows)

    @staticmethod
    def _prune(window: deque[float], per_seconds: float, now: float) -> None:
        cutoff = now - per_seconds
        while window and window[0] <= cutoff:
            window.popleft()

    def _evict_idle(self, now: float, per_seconds: float) -> None:
        # Drop keys whose newest call is outside the window; if none qualify, drop the stalest key.
        cutoff = now - per_seconds
        idle = [k for k, w in self._windows.items() if not w or w[-1] <= cutoff]
        for key in idle:
            del self._windows[key]
        if len(self._windows) >= self._max_keys:
            stalest = min(self._windows, key=lambda k: self._windows[k][-1] if self._windows[k] else float("-inf"))
            del self._windows[stalest]
