# Infinity

A URL shortener built to go deep on real backend engineering — caching correctness, concurrency behavior, and honest benchmarking — rather than to just ship a working redirect endpoint. The feature set is intentionally simple; the point was understanding what's underneath it.

## What this actually is

Most URL shortener tutorials stop at "map a short code to a long URL." This project instead treats that as the starting point, and spends its real effort on the stuff production systems actually have to get right: cache correctness, what happens under concurrent load, where a system's real ceiling is, and why a benchmark result might not mean what it looks like it means.

Every finding below was arrived at by actually breaking things, measuring them, and — more than once — discovering the first explanation was wrong.

## Features

- `POST /shorten` — idempotent short URL creation (the same long URL always returns the same short code)
- `GET /{short_code}` — redirect, backed by a two-level cache
- `GET /stats` — live cache hit-rate visibility (L1 / L2 / DB split)
- Multi-level caching: in-process LRU (L1) → Redis (L2) → PostgreSQL (source of truth)
- Fully async request path (no blocking calls on the hot path)

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI (async) |
| Database | PostgreSQL, via async SQLAlchemy (`asyncpg`) |
| Cache (L2) | Redis, via `redis.asyncio` |
| Cache (L1) | Hand-built in-process LRU with TTL |
| Load testing | `hey`, `vegeta`, and a custom Zipf-weighted multi-key tester |

## Architecture

```
Client
  │
  ▼
FastAPI (async, multiple workers)
  │
  ├─► L1 cache (in-process LRU, per worker) ─── hit? return immediately
  │
  ├─► L2 cache (Redis) ─── hit? promote to L1, return
  │
  └─► PostgreSQL (source of truth) ─── populate L1 + L2, return
```

## Performance

Benchmarked on a personal laptop (Intel i5-1155G7, 8 threads, ~7GB RAM, NVMe SSD) — not dedicated server hardware, and not a simulator. All numbers below are from real `hey`/`vegeta` runs against a running instance; full methodology and every intermediate result (including the wrong turns) are in [`BENCHMARK.md`](./BENCHMARK.md).

| Configuration | Throughput | Avg latency |
|---|---|---|
| Sync, buggy cache (original) | ~1,550 req/sec | ~58ms |
| Sync, cache fixed, 8 workers | ~8,300 req/sec | ~11.2ms |
| **Async + L1 cache, single hot key** | **~20,000+ req/sec** | **~5ms** |
| **Async + L1 cache, 20 keys, Zipf-weighted, real multi-key load** | **~20,480 req/sec** | **~4.5ms** |

**Important caveat:** these numbers reflect a cache-hit-heavy workload (99%+ L1 hit rate in the multi-key test) — realistic for how link shorteners actually get used (a small number of links account for most clicks), but not representative of cold-cache or cold-database throughput. Cold-path/database-optimization benchmarking is in progress — see Roadmap.

One concrete result worth highlighting: the sync version collapsed under high concurrency (~983 req/sec at 500 concurrent connections, from a healthy ~6,300 req/sec at lower concurrency). The async rewrite removed that collapse entirely — throughput stayed in the 15,000–22,000 req/sec range from 100 all the way up to 2,000 concurrent connections, with latency degrading gracefully instead of falling off a cliff.

## Notable engineering findings

A few things this project actually uncovered, not just built:

- **A cache that was never being used.** An early version read from Redis on every redirect but never checked the result before falling through to Postgres — Redis was fully wired up and completely inert. Found via benchmarking, not code review; fixing it roughly quadrupled throughput.
- **A "dropped requests" mystery that wasn't real.** A consistent ~4% of requests appeared to fail at higher concurrency. Two plausible OS-level causes (thread pool exhaustion, kernel socket backlog limits) were tested and ruled out with direct evidence before the real cause turned out to be the load-testing tool rounding its own request count down to a clean multiple of concurrency — not a server-side bug at all.
- **A load-testing tool silently following a redirect to the real internet.** A multi-key benchmark reported 100% failure. The actual cause: the benchmarking tool followed the app's redirect by default, all the way out to the real `example.com` (used as filler destination data), and reported that unrelated site's 404 as if the app under test had failed.
- **The collapse point disappeared entirely** after moving from a thread-pool-bound sync architecture to a fully async one — documented with a full before/after concurrency sweep.

Full writeups of all of these, including the dead ends, are in the running project log (linked below).

## Running it locally

```bash
git clone <repo-url>
cd Infinity 

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set up PostgreSQL and Redis locally, then create `.env`:
```
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<dbname>
```

Run it:
```bash
uvicorn app.main:app --workers 8
```

## Benchmarking

```bash
# Single-key throughput
hey -n 5000 -c 100 -disable-redirects http://127.0.0.1:8000/<short_code>

# Multi-key, realistic (Zipf-weighted) traffic, with cache hit-rate visibility
python loadtest.py -n 5000 -c 100 -k 20 --skew 1.2

# Multi-key, at full (non-Python-bottlenecked) throughput
python gen_vegeta_targets.py -k 20 --skew 1.2 -o targets.txt
vegeta attack -targets=targets.txt -rate=0 -max-workers=100 -redirects=-1 -duration=10s | vegeta report
```

## Project structure

```
app/
  main.py          — routes, request handling, cache orchestration
  database.py       — async SQLAlchemy engine + session setup
  models.py         — ORM models
  schemas.py         — Pydantic request/response schemas
  redis_client.py    — async Redis (L2) client
  l1_cache.py         — in-process LRU cache (L1)
  stats.py            — cache hit-rate counters
  utils.py             — short code generation
gen_vegeta_targets.py  — Zipf-weighted target file generator for vegeta
loadtest.py             — custom multi-key async load tester
BENCHMARK.md            — full benchmark history and methodology
```

## Honest limitations

This is a portfolio/learning project, and these gaps are known rather than accidental:

- No authentication — anyone can create or look up links
- No rate limiting yet
- No automated tests yet
- No collision-retry on short code generation
- Single machine, single region — no horizontal scaling or CDN layer
- Cold-path (uncached) throughput has not yet been isolated and benchmarked separately from cache-hit throughput

## Roadmap

- [ ] Cold-path benchmarking (isolate true database-only throughput)
- [ ] Database optimization (index verification, connection pool tuning)
- [ ] Rate limiting
- [ ] Async click tracking / analytics (queue-based, off the hot path)
- [ ] Basic automated tests
- [ ] Horizontal scaling (multiple instances + load balancer)
