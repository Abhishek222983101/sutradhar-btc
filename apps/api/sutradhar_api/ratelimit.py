"""In-process sliding-window rate limits (one API process per deployment, blueprint §12.7)."""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, *, max_keys: int = 50_000) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def hit(self, bucket: str, key: str, *, limit: int, window_s: float) -> int | None:
        """Record one hit. Returns None if allowed, else the seconds until a slot frees up."""
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > self._max_keys:
                self._prune(now, window_s)
            hits = self._hits.setdefault((bucket, key), deque())
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(hits[0] + window_s - now) + 1)
            hits.append(now)
            return None

    def _prune(self, now: float, window_s: float) -> None:
        stale = [k for k, v in self._hits.items() if not v or v[-1] <= now - window_s]
        for k in stale:
            del self._hits[k]
        if len(self._hits) > self._max_keys:  # still flooded: drop everything rather than grow without bound
            self._hits.clear()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
