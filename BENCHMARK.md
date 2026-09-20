# Benchmarks

Performance benchmarks for the URL shortener service. All tests run locally against `http://127.0.0.1:8000`.

> **Update note:** the original Redis section of this document (further below) concluded Redis was not beneficial at this scale. That conclusion was based on a benchmark run against a version of the code with a caching bug — the redirect handler read from Redis but never checked the result before falling through to Postgres, so "Redis (Warm)" numbers below were actually measuring Postgres + a wasted Redis round-trip, not an actual cache hit. The bug has been fixed; corrected numbers are in the **"Redis — Corrected Results"** section near the end. The original sections are left intact below for the historical record, since the reasoning in them was sound given the (broken) data available at the time.

---

## Baseline — DB Lookup (No Cache)

This is all for the relational database because we are using Postgres (just for MVP, not considered for scaling).
Redirect resolution hitting the database directly via B-tree index. No in-memory caching layer.

**Tool:** [`hey`](https://github.com/rakyll/hey)
**Command:**
```
hey -n 5000 -c 100 -disable-redirects http://127.0.0.1:8000/orAXTk
```

### Summary

| Metric           | Value       |
|------------------|-------------|
| Total requests   | 5,000       |
| Concurrency      | 100         |
| Total time       | 15.75 secs  |
| Requests/sec     | 317.45      |
| Avg latency      | 305.0 ms    |
| Median (p50)     | 287.5 ms    |
| p95              | 494.2 ms    |
| p99              | 657.3 ms    |
| Fastest          | 9.1 ms      |
| Slowest          | 1036.2 ms   |
| Status           | 307 ✓ (all) |

### Latency Distribution

```
  9ms  [1]     |
112ms  [124]   |■■■
214ms  [950]   |■■■■■■■■■■■■■■■■■■■■
317ms  [1874]  |■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■  ← peak
420ms  [1337]  |■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
523ms  [540]   |■■■■■■■■■■■■
625ms  [119]   |■■■
728ms  [19]    |
831ms  [15]    |
933ms  [11]    |
1036ms [10]    |
```

### Time Breakdown (avg)

| Phase       | Time      | % of total |
|-------------|-----------|------------|
| DNS + dialup | 0.3 ms   | ~0.1%      |
| Request write | 0.0 ms  | ~0%        |
| **Response wait** | **304.6 ms** | **~99.9%** |
| Response read | 0.1 ms  | ~0%        |

> Nearly all latency is server-side. Network and I/O are negligible.

### Notes

- The distribution peaks at ~317ms with a right tail reaching 1s+ — classic queuing behavior under high concurrency, not raw DB speed
- `resp wait` consuming 99.9% of latency points to worker/connection pool contention at c=100, not B-tree lookup overhead
- The long tail (p99 = 657ms vs p50 = 287ms) suggests some requests queue behind busy workers

---

## Multi-Worker Benchmark — 4 Workers

### Setup

* Backend: FastAPI (Uvicorn)
* Workers: 4
* Database: PostgreSQL (local)
* Test Tool: hey
* Endpoint: `/{short_code}` (redirect)
* Redirects disabled to measure backend latency only

**Command:**

```
hey -n 5000 -c 100 -disable-redirects http://127.0.0.1:8000/4FmAo3
```

### Results

| Metric         | Value       |
| -------------- | ----------- |
| Total Requests | 5,000       |
| Concurrency    | 100         |
| Total Time     | 2.60 sec    |
| Requests/sec   | 1918.83     |
| Avg Latency    | 49.5 ms     |
| p50            | 47.0 ms     |
| p95            | 80.7 ms     |
| p99            | 115.6 ms    |
| Fastest        | 1.4 ms      |
| Slowest        | 175.4 ms    |
| Status         | 307 ✓ (all) |

### Latency Distribution

```
0.001 [1]     |
0.019 [116]   |■■
0.036 [843]   |■■■■■■■■■■■■■■
0.054 [2409]  |■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
0.071 [1165]  |■■■■■■■■■■■■■■■■■■■
0.088 [298]   |■■■■■
0.106 [90]    |■
0.123 [31]    |■
0.141 [25]    |
0.158 [14]    |
0.175 [8]     |
```

### Observations

* Significant performance improvement compared to single-worker setup
* Average latency reduced from ~300ms → ~50ms (~6x improvement)
* Throughput increased from ~317 req/sec → ~1900 req/sec (~6x improvement)
* Tail latency (p99) reduced drastically (~650ms → ~115ms)
* Latency distribution is tight with minimal long-tail behavior

### Analysis

* The primary bottleneck in the baseline system was **worker contention**, not database performance
* Increasing worker count allowed parallel request handling, reducing queueing delays
* Database lookups are fast and not yet a limiting factor under current load
* System demonstrates good scaling behavior with increased concurrency

### Conclusion

* Multi-worker configuration significantly improves system performance
* Current architecture (FastAPI + PostgreSQL) is sufficient for moderate traffic (~2k RPS)
* ~~Introducing Redis at this stage would be a **premature optimization**~~ — see "Redis — Corrected Results" below; this conclusion was based on a broken cache implementation.

### Next Steps

* Test higher concurrency (200–500 users)
* Evaluate performance under cold-cache conditions
* Benchmark write-heavy workloads (`/shorten`)
* Introduce Redis caching when database becomes a bottleneck

### Problem with workers

* Memory
  4 workers → 4x memory usage

* DB connections
  4 workers → multiple DB connections

* CPU limit
  4 CPU cores → ideal ≈ 4 workers (this machine actually has **8 cores** — see worker-scaling section below, this assumption undercounted available capacity)

* Workers dont make you app faster they make it more capable of handling multiple requests simultaneously.

---

## High Concurrency Stress Test — c=500

### Results

| Metric      | Value   |
| ----------- | ------- |
| RPS         | ~983    |
| Avg Latency | ~339 ms |
| p99         | ~881 ms |

### Observations

* Throughput decreased significantly compared to lower concurrency levels
* Average latency increased ~5x compared to c=200
* Tail latency (p99) exceeded 800ms, indicating severe queueing
* Response wait time dominates total latency, suggesting request backlog

### Analysis

* System has reached saturation point at high concurrency (c=500)
* Worker processes are overloaded, leading to request queue buildup
* CPU/worker capacity is the primary bottleneck
* Database is not the limiting factor at this stage

### Conclusion

* Optimal operating range: ~200–250 concurrent users (~2500 RPS)
* Beyond this point, performance degrades due to worker saturation
* Scaling requires:
  * increasing worker count
  * adding CPU resources
  * or horizontal scaling across multiple instances

---

# Redis Caching — Original Benchmark & Analysis (superseded — see corrected results below)

## 📊 Test Setup

* Tool: `hey`
* Endpoint: `/{short_code}` (redirect)
* Redirects disabled
* Environment:
  * FastAPI + Uvicorn (4 workers)
  * PostgreSQL (local)
  * Redis (local)
* Load: 5000 requests, concurrency = 100

## 🚀 Baseline — Without Redis

| Metric      | Value   |
| ----------- | ------- |
| RPS         | ~1919   |
| Avg Latency | ~49 ms  |
| p50         | ~47 ms  |
| p95         | ~80 ms  |
| p99         | ~115 ms |

## ⚠️ Redis (Cold Cache) — measured against the buggy cache implementation

| Metric      | Value   |
| ----------- | ------- |
| RPS         | ~1323   |
| Avg Latency | ~66 ms  |
| p99         | ~339 ms |

## ✅ Redis (Warm Cache) — measured against the buggy cache implementation

| Metric      | Value       |
| ----------- | ----------- |
| RPS         | ~1500–1650  |
| Avg Latency | ~57–61 ms   |
| p99         | ~125–150 ms |

## 📈 Comparative Summary (original, pre-fix)

| Scenario     | RPS   | Avg Latency | p99     |
| ------------ | ----- | ----------- | ------- |
| No Redis     | ~1919 | ~49 ms      | ~115 ms |
| Redis (Cold) | ~1323 | ~66 ms      | ~339 ms |
| Redis (Warm) | ~1550 | ~58 ms      | ~130 ms |

**Why these numbers were misleading:** the redirect handler fetched `cached_url` from Redis but never branched on it — every request, cache hit or not, fell through to a full Postgres query regardless. So "Redis (Warm)" above wasn't measuring a cache hit; it was measuring Postgres query time *plus* a wasted Redis round-trip on top of it, which is exactly why it came in slower than the no-cache baseline. The conclusions below ("Redis introduces overhead," "not beneficial in this setup") were reasonable given this data — the data itself just wasn't measuring what it claimed to.

---

# Redis — Corrected Results (post cache-fix)

## The Bug

```python
# Before (bug): cached_url fetched but never used
cached_url = redis_client.get(short_code)
db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
...

# After (fix): cache hit short-circuits before the DB is ever touched
cached_url = redis_client.get(short_code)
if cached_url:
    return RedirectResponse(cached_url)
db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
```

## Results — 4 Workers, c=100

| Run              | RPS   | Avg Latency | p99     |
| ----------------- | ----- | ----------- | ------- |
| Cold (`FLUSHALL` before run) | ~6,303 | ~15.5 ms | ~28 ms |
| Warm (immediate re-run)      | ~6,421 | ~15.2 ms | ~25 ms |

Cold and warm come out nearly identical — not because caching doesn't matter, but because `FLUSHALL` only empties Redis *before* the run starts. Under `c=100` concurrency, the very first request repopulates the cache almost instantly, so by request #2 the "cold" run is already >99% warm-cache traffic. This isn't a controlled cold-vs-warm comparison; both runs are effectively warm-cache throughput.

**Actual before/after (same 4-worker, c=100 config):**

| Metric      | Pre-fix ("Redis Warm") | Post-fix |
| ----------- | ----------------------- | -------- |
| RPS         | ~1,550                  | **~6,400** |
| Avg Latency | ~58 ms                  | **~15 ms** |
| p99         | ~130 ms                 | **~25 ms** |

Roughly a **4x throughput increase** once the cache was actually being used.

## Why the original "Redis doesn't help" conclusion still has a grain of truth

Even now, on a local, indexed Postgres instance, the *absolute* gap between a cache hit and a cache miss on this machine is small in wall-clock terms — a local indexed lookup is already fast. The bug masked the real comparison entirely, but the original insight that "Redis matters more under network latency to a remote DB, or DB load under sustained traffic, than on a quiet local Postgres" is still directionally correct — it just wasn't actually being tested by the original benchmark.

---

# Concurrency Sweep (post cache-fix, 4 workers)

| Concurrency | RPS   | Avg Latency | p99     | Completed |
| ----------- | ----- | ------------| ------- | --------- |
| 100         | 6,562 | 14.5 ms     | 21.9 ms | 5000/5000 |
| 150         | 6,331 | 23.1 ms     | 39.9 ms | 4950/5000* |
| 160         | 6,316 | 24.2 ms     | 48.6 ms | 4960/5000* |
| 250         | 6,294 | 37.4 ms     | 113.7 ms| 5000/5000 |
| 300         | 5,832 | 46.8 ms     | 178.7 ms| 4800/5000* |
| 400         | 5,905 | 59.0 ms     | 234.0 ms| 4800/5000* |
| 500         | ~983  | ~339 ms     | ~881 ms | —         |

\* See "Note on incomplete-looking results" below — these are not actual dropped requests.

**Finding:** throughput stays flat (~6,300–6,500 RPS) from c=100 through c=250, with latency climbing steadily rather than staying flat — the signature of a system already saturated around c=100, not one with clean headroom up to a specific thread count. A hypothesis that the 4-worker × 40-thread default (160 total thread capacity) would produce a sharp cliff exactly at c=160 did not hold — no cliff appears there. The real, sharp collapse happens somewhere between c=400 and c=500, not yet narrowed further.

---

# Worker Scaling — 4 vs 8 Workers

Machine has **8 CPU cores** (`nproc`); original benchmarks above were run with only 4 workers.

## Baseline (c=100)

| Workers | RPS    | Avg Latency | p99     |
| ------- | ------ | ------------| ------- |
| 4       | 6,562  | 14.5 ms     | 21.9 ms |
| 8       | ~8,300 | ~11.2 ms    | ~22.8 ms|

~27% throughput increase from matching worker count to core count, confirmed across repeated runs (8,321 / 8,250 req/sec). This confirms throughput at c=100 was partly CPU/worker-bound, not purely capped by thread-pool size — if it were purely thread-bound, adding workers wouldn't have moved a number already well under the old 160-thread ceiling.

## Higher concurrency, 8 workers

| Concurrency | RPS (4 workers) | RPS (8 workers) | p99 (4w) | p99 (8w) |
| ----------- | ---------------- | ---------------- | -------- | -------- |
| 300         | 5,832            | 7,108             | 178.7 ms | 117.4 ms |
| 400         | 5,905            | 6,330             | 234.0 ms | 137.1 ms |

Both throughput and tail latency improved meaningfully with more workers at higher concurrency.

---

# Note on "Incomplete" Results at c=150+ — Resolved

Several runs above show fewer completed responses than requests sent (e.g. 4800/5000 at c=300). This was investigated as a potential dropped-request bug and is **not actually one**. Root cause: `hey -n 5000 -c 300` distributes total requests across concurrent workers, and 5000 doesn't divide evenly by 300 — `hey` rounds down to the nearest clean multiple (`300 × 16 = 4800`) and never sends the remaining 200 requests in the first place.

Confirmed by re-running with aligned numbers:
```
hey -n 4800 -c 300 -disable-redirects http://127.0.0.1:8000/ly1G6y
→ 4800 / 4800 completed (100%)
```

Two other explanations were investigated and ruled out with direct evidence before finding this:
- **Thread-pool/worker exhaustion** — ruled out: doubling workers (4→8) had zero effect on the gap count.
- **`ulimit -n` (file descriptors)** — checked: 1024, nowhere near being challenged by 300–400 connections.
- **`net.core.somaxconn` (kernel backlog cap)** — checked: 4096, also nowhere near being challenged.

The server never dropped a single request at any concurrency level tested up to c=400.

---

# Final Takeaway

> Performance optimizations must be driven by measured bottlenecks, not assumptions — and the measurement itself has to be verified before trusting its conclusions. Two separate investigations in this document (the Redis caching bug, and the "dropped requests" that turned out to be a benchmarking-tool rounding artifact) were cases where the numbers were collected carefully and still led to a wrong conclusion, because the thing being measured wasn't what it appeared to be.
