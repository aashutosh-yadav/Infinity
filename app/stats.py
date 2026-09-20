"""
Simple in-process counters for cache hit-rate visibility.

Note the same caveat that applies to the L1 cache applies here: with
multiple uvicorn workers, each worker process gets its OWN separate copy
of these counters (they don't share memory). /stats reflects only the
worker process that happened to handle that particular request -- not a
true aggregate across all workers. Good enough to see the *shape* of hit
rates; not a substitute for a real shared metrics store (Prometheus, etc.)
if you want a true cross-worker total later.
"""


class Stats:
    def __init__(self):
        self.l1_hits = 0
        self.l2_hits = 0
        self.db_hits = 0
        self.misses = 0  # short code not found at all

    def total(self) -> int:
        return self.l1_hits + self.l2_hits + self.db_hits + self.misses

    def as_dict(self) -> dict:
        total = self.total()

        def rate(count: int) -> float:
            return round(count / total, 4) if total else 0.0

        return {
            "total_requests": total,
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "db_hits": self.db_hits,
            "not_found": self.misses,
            "l1_hit_rate": rate(self.l1_hits),
            "l2_hit_rate": rate(self.l2_hits),
            "db_hit_rate": rate(self.db_hits),
        }


stats = Stats()
