# High-Performance URL Shortener

A production-inspired, read-heavy URL shortener built with **FastAPI**, **PostgreSQL**, and **Redis**, with a focus on performance engineering, scalability, and system design.

This project is an engineering exploration rather than a feature-driven product. The goal is to understand real-world system behavior through benchmarking, bottleneck analysis, and iterative optimization — not to accumulate features.

## Features

- High-performance redirect service (~1,900 RPS under load)
- Cache-aside Redis integration (experimentally evaluated)
- Detailed performance benchmarking using `hey`
- Idempotent URL shortening (same URL maps to the same short code)
- Simple frontend for manual testing

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Database | PostgreSQL (indexed lookups) |
| Cache | Redis (optional, evaluated) |
| Server | Uvicorn (multi-worker) |
| Benchmarking | hey |

## Architecture

```
Client
  ↓
FastAPI (Workers)
  ↓
Redis (Cache)
  ↓
PostgreSQL (Source of Truth)
```

## Performance Highlights

| Scenario | RPS | Avg Latency | p99 |
|---|---|---|---|
| Single Worker | ~317 | ~305 ms | ~657 ms |
| 4 Workers | ~1,919 | ~49 ms | ~115 ms |
| Redis (Warm) | ~1,500 | ~58 ms | ~130 ms |

## Key Insights

### 1. Worker Scaling Outweighs Other Optimizations
Moving from 1 to 4 workers improved throughput by roughly 6x. The primary bottleneck was worker contention, not the database.

### 2. Redis Did Not Improve Performance (Yet)
In this local setup, Redis introduced additional overhead without a corresponding benefit. PostgreSQL queries were already fast, since they were indexed and running locally, so the result was lower throughput and slightly higher latency.

### 3. Caching Is Context-Dependent
Caching does not universally improve performance. Redis becomes valuable primarily when:
- The database is remote (network latency dominates)
- The database is under heavy load
- The system is distributed across multiple instances

### 4. System Saturation Behavior
At high concurrency (c=500), RPS dropped to ~983 and p99 latency exceeded ~800 ms, driven by request queueing and CPU saturation.

## Benchmarking

All tests were performed using:

```bash
hey -n 5000 -c 100 -disable-redirects http://127.0.0.1:8000/{short_code}
```

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/aashutosh-yadav/Infinity
cd Infinity
```

### 2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the backend
```bash
uvicorn app.main:app --workers 4 --reload
```

### 5. Open the frontend
```bash
open app/frontend/index.html
```

## What This Project Demonstrates

- Performance benchmarking and analysis
- Identifying real bottlenecks rather than assumed ones
- Understanding concurrency and worker scaling
- Critically evaluating caching strategies
- Applying real-world system design thinking

## Future Improvements

- Deploy the database remotely to validate caching benefits
- Add a load balancer and multi-instance setup
- Implement an analytics pipeline for click tracking
- Introduce distributed ID generation (Snowflake)
- Add rate limiting and abuse protection

## Key Takeaway

> Optimization must be driven by measured bottlenecks, not assumptions.

## Contributing

If you find this useful, consider starring the repository, or forking it to experiment further.
