"""Tiny bounded TTL caches for expensive read-only computations."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable
from typing import Any


class TTLCache:
    def __init__(self, maxsize: int = 256, ttl_seconds: float = 300.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._data: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < time.monotonic():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self.maxsize:
                # Drop the entry closest to expiry first.
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (time.monotonic() + self.ttl, value)

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


# Scenario risk depends only on (rainfall, duration, built-up pct).
scenario_cache = TTLCache(maxsize=64, ttl_seconds=300.0)
