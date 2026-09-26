# Infinity

A URL shortener built to go deep on real backend engineering — caching correctness, concurrency behavior, database connection limits, and honest benchmarking — rather than to just ship a working redirect endpoint. The feature set is intentionally simple; the point was understanding, and measuring, what's underneath it.

## What this actually is

Most URL shortener tutorials stop at "map a short code to a long URL." This project treats that as the starting point. Every claim below was arrived at by actually breaking something, measuring it, and — more than once — discovering the first explanation was wrong. That process (documented in full in the running project log) is the actual point of the project, not the feature list.

## Features

- `POST /shorten` — idempotent short URL creation (the same long URL always returns the same short code)
- `GET /{short_code}` — redirect, backed by a two-level cache
- `GET /stats` — live cache hit-rate visibility (L1 / L2 / DB split)
- Fully async request path — no blocking calls on the hot path
- Multi-level caching: in-process LRU (L1) → Redis (L2) → PostgreSQL (source of truth)
- A live, in-browser benchmark tool in the frontend — fires real concurrent requests from your own browser and shows real, measured throughput/latency, not canned numbers

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI (async) |
| Database | PostgreSQL, via async SQLAlchemy (`asyncpg`) |
| Cache (L2) | Redis, via `redis.asyncio` |
| Cache (L1) | Hand-built in-process LRU with TTL |
| Load testing | `hey`, `vegeta`, plus two custom tools (below) |

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

**Note on workers:** the app runs with multiple `uvicorn` worker processes. Each worker is a separate OS process with its **own** L1 cache and its **own** `/stats` counters — they are not shared. `/stats` reflects whichever single worker answered that particular request, not a true sum across all workers.

## Performance

Benchmarked on a personal laptop — Intel i5-1155G7 (11th Gen, 8 threads @ 2.5GHz), ~6.9GB usable RAM, NVMe SSD — actively running a full desktop session throughout testing, not a dedicated or isolated server. All numbers are from real `hey`/`vegeta` runs against a running instance. Full methodology, every intermediate result, and every wrong turn are in [`BENCHMARK.md`](./BENCHMARK.md).

| Path | Throughput | Avg latency | Success rate |
|---|---|---|---|
| **Hot** (cache hit, realistic multi-key traffic) | ~20,400 req/sec | ~4.5ms | 100% |
| **Cold** (guaranteed cache miss, straight to PostgreSQL) | ~3,500 req/sec | ~28ms | 100% |

These are two genuinely different numbers, measured separately and on purpose — see "Notable engineering findings" below for why that distinction matters and how the cold-path number was obtained.

One additional result worth highlighting: an earlier, sync (non-async) version of this app collapsed under high concurrency — throughput fell to ~983 req/sec at 500 concurrent connections, down from a healthy ~6,300 req/sec at lower concurrency, with p99 latency blowing out to ~881ms. After the async rewrite, that collapse disappeared entirely: throughput stayed in the 15,000–22,000 req/sec range from 100 concurrent connections all the way up to 2,000, with latency degrading gracefully instead of falling off a cliff.

## Notable engineering findings

A few things this project actually uncovered, not just built:

- **A cache that was never being used.** An early version read from Redis on every redirect but never checked the result before falling through to Postgres — Redis was fully wired up and completely inert. Found via benchmarking, not code review; fixing it roughly quadrupled throughput.
- **A "dropped requests" mystery that wasn't real.** A consistent ~4% of requests appeared to fail at higher concurrency. Two plausible OS-level causes (thread pool exhaustion, kernel socket backlog limits) were tested and ruled out with direct evidence before the real cause turned out to be the load-testing tool rounding its own request count down to a clean multiple of concurrency — not a server-side bug at all.
- **A load-testing tool silently following a redirect to the real internet.** A multi-key benchmark reported 100% failure. The actual cause: the benchmarking tool followed the app's redirect by default, all the way out to the real `example.com` (used as filler destination data), and reported that unrelated site's 404 as if the app under test had failed.
- **A cold-path benchmark that exposed a real connection-limit bug the hot path could never have found.** Cache-hit traffic never touches the database connection pool at all, so a bug in the pool configuration sat invisible through every earlier benchmark. Running genuinely uncached traffic (thousands of never-before-seen short codes, seeded directly into Postgres) immediately produced `TooManyConnectionsError` — the app's connection pool, multiplied across worker processes, could request far more simultaneous connections than PostgreSQL's own `max_connections` allowed. Fixed by right-sizing the app's pool and raising the database's connection ceiling to match.
- **The collapse point disappeared entirely** after moving from a thread-pool-bound sync architecture to a fully async one — documented with a full before/after concurrency sweep.

Full writeups of all of these, including the dead ends, are in the running project log (linked below).

## Live demo

The frontend includes a "Run Benchmark" button that fires real concurrent requests from your own browser at the running backend and shows live, measured throughput and latency — not a static number. It's honestly labeled: browser-driven numbers will be noticeably lower than the table above, because browsers hard-cap concurrent connections per origin in a way dedicated load-testing tools aren't. The gap itself is part of the point — it's demonstrating what a real client can drive against this server, not trying to match a purpose-built benchmarking tool.

## Running it locally

```bash
git clone <repo-url>
cd infinity

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

Visit `http://127.0.0.1:8000` — the live benchmark tool is right there on the page.

A `Dockerfile` and `docker-compose.yml` also exist in this repo for a one-command Postgres + Redis + app setup, but aren't the primary supported path yet — the app is actively developed and benchmarked against a plain local install as above.

## Benchmarking

```bash
# Single-key throughput (hot path)
hey -n 5000 -c 100 -disable-redirects http://127.0.0.1:8000/<short_code>

# Multi-key, realistic (Zipf-weighted) hot-path traffic, with cache hit-rate visibility
python loadtest.py -n 5000 -c 100 -k 20 --skew 1.2

# Multi-key hot-path, at full (non-Python-bottlenecked) throughput
python gen_vegeta_targets.py -k 20 --skew 1.2 -o targets.txt
vegeta attack -targets=targets.txt -rate=0 -max-workers=100 -redirects=-1 -duration=10s | vegeta report

# True cold-path throughput (guaranteed cache misses, direct to Postgres)
python seed_cold_data.py -n 50000 -o cold_targets.txt
vegeta attack -targets=cold_targets.txt -rate=0 -max-workers=100 -redirects=-1 -duration=5s | vegeta report
```

**Important for cold-path testing:** keep the attack's total request count under the number of codes you seeded, or `vegeta` will cycle back and start hitting already-cached codes — no longer a valid cold-path measurement. `seed_cold_data.py` prints a reminder of this every time it runs.

## Project structure

```
app/
  main.py          — routes, request handling, cache orchestration
  database.py      — async SQLAlchemy engine, session setup, connection pool config
  models.py        — ORM model
  schemas.py       — Pydantic request/response schemas
  redis_client.py  — async Redis (L2) client, host/port configurable via env vars
  l1_cache.py       — in-process LRU cache with TTL (L1)
  stats.py           — cache hit-rate counters
  utils.py            — short code generation
  frontend/index.html — live dashboard + in-browser benchmark tool
loadtest.py              — custom async multi-key load tester (Zipf-weighted); useful for hit-rate visibility, bottlenecked by its own Python overhead for raw throughput
gen_vegeta_targets.py    — seeds short codes via the API, writes a Zipf-weighted vegeta target file
seed_cold_data.py        — bulk-inserts unique short codes directly into Postgres and writes a vegeta target file guaranteed to produce cache misses
BENCHMARK.md             — full benchmark history and methodology, including superseded results kept for the record
Dockerfile, docker-compose.yml — Postgres + Redis + app, built and working, not yet the primary dev workflow
```

## Honest limitations

This is a portfolio/learning project, and these gaps are known rather than accidental:

- No authentication — anyone can create or look up links
- No rate limiting yet
- No automated tests yet
- No collision-retry on short code generation
- Single machine, single region — no horizontal scaling or CDN layer
- A small number of residual errors (well under 1% of requests) appeared during early cold-path load testing and have not yet been fully root-caused, though the dominant failure mode (database connection exhaustion) is confirmed fixed
- L1 cache TTL behavior has not been specifically load-tested at the expiry boundary

## Roadmap

- [ ] Resolve remaining residual cold-path errors
- [ ] PgBouncer (or similar) in front of PostgreSQL, as the more scalable answer to connection-limit tuning than hand-sizing the app's pool
- [ ] Rate limiting
- [ ] Async click tracking / analytics (queue-based, off the hot path)
- [ ] Basic automated tests
- [ ] Collision-retry on short code generation
- [ ] Horizontal scaling (multiple instances + load balancer)
- [ ] Make Docker Compose the default local dev path
