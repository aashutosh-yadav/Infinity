# Benchmarks

Performance benchmarks for the URL shortener service. All tests run locally against `http://127.0.0.1:8000`.

---

## Baseline — DB Lookup (No Cache)

This is all for the realational database because we are using postgress.(just for MVP , not considerd scalling). 
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
* Endpoint: `/ {short_code}` (redirect)
* Redirects disabled to measure backend latency only

**Command:**

```
hey -n 5000 -c 100 -disable-redirects http://127.0.0.1:8000/4FmAo3
```

---

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

---

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

---

### Observations

* Significant performance improvement compared to single-worker setup
* Average latency reduced from ~300ms → ~50ms (~6x improvement)
* Throughput increased from ~317 req/sec → ~1900 req/sec (~6x improvement)
* Tail latency (p99) reduced drastically (~650ms → ~115ms)
* Latency distribution is tight with minimal long-tail behavior

---

### Analysis

* The primary bottleneck in the baseline system was **worker contention**, not database performance
* Increasing worker count allowed parallel request handling, reducing queueing delays
* Database lookups are fast and not yet a limiting factor under current load
* System demonstrates good scaling behavior with increased concurrency

---

### Conclusion

* Multi-worker configuration significantly improves system performance
* Current architecture (FastAPI + PostgreSQL) is sufficient for moderate traffic (~2k RPS)
* Introducing Redis at this stage would be a **premature optimization**

---

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
  4 CPU cores → ideal ≈ 4 workers  

* Workers dont make you app faster they make it more capable of handling multiple requests simultaneously .


## High Concurrency Stress Test — c=500

### Results

| Metric      | Value   |
| ----------- | ------- |
| RPS         | ~983    |
| Avg Latency | ~339 ms |
| p99         | ~881 ms |

---

### Observations

* Throughput decreased significantly compared to lower concurrency levels
* Average latency increased ~5x compared to c=200
* Tail latency (p99) exceeded 800ms, indicating severe queueing
* Response wait time dominates total latency, suggesting request backlog

---

### Analysis

* System has reached saturation point at high concurrency (c=500)
* Worker processes are overloaded, leading to request queue buildup
* CPU/worker capacity is the primary bottleneck
* Database is not the limiting factor at this stage

---

### Conclusion

* Optimal operating range: ~200–250 concurrent users (~2500 RPS)
* Beyond this point, performance degrades due to worker saturation
* Scaling requires:

  * increasing worker count
  * adding CPU resources
  * or horizontal scaling across multiple instances












