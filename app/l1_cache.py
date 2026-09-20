"""
A small in-process LRU cache with per-entry TTL.

This sits in front of Redis as an L1 cache: the hottest short codes get
served straight from app memory, skipping the network round-trip to Redis
entirely. Real-world URL shortener traffic is heavily power-law distributed
(a small fraction of links get most of the clicks), so this is where a lot
of the cheap wins for a redirect-heavy workload actually live.

Built by hand rather than pulling in a library (e.g. cachetools) since the
point of this project is understanding the mechanism, not just having it.
"""

import time
import asyncio
from collections import OrderedDict


class LRUCache:
    def __init__(self, max_size: int = 1024, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            value, expires_at = entry
            if expires_at < time.monotonic():
                # expired -> treat as a miss and evict it
                del self._store[key]
                return None

            # move to the end = "most recently used"
            self._store.move_to_end(key)
            return value

    async def set(self, key: str, value: str) -> None:
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)

            self._store[key] = (value, time.monotonic() + self.ttl_seconds)

            if len(self._store) > self.max_size:
                # evict the least recently used entry (the first one)
                self._store.popitem(last=False)

    def __len__(self) -> int:
        return len(self._store)
