# Benchmarks

Performance benchmarks for the URL shortener service. All tests run locally against `http://127.0.0.1:8000`.

---

## Baseline — DB Lookup (No Cache)

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

## Roadmap

| Test                              | Status      |
|-----------------------------------|-------------|
| Baseline — DB only                | ✅ Done      |
| In-memory cache (LRU)             | ⬜ Pending   |
| Cache + DB fallback               | ⬜ Pending   |
| Write path (`/shorten`) load test | ⬜ Pending   |
| Distributed load (multi-node)     | ⬜ Pending   |