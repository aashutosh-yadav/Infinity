# ⚡ URL Shortener — Engineering Deep Dive

> A URL shortener built not to demonstrate features, but to solve hard distributed systems problems.
> Every optimization is measured. Every tradeoff is documented.

---

## Table of Contents

- [The Big Picture](#the-big-picture)
- [Hard Engineering Problems Solved](#hard-engineering-problems-solved)
- [Architecture](#architecture)
- [Database Design](#database-design)
- [API Reference](#api-reference)
- [Benchmarks](#benchmarks)
- [System Design Decisions](#system-design-decisions)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Running Load Tests](#running-load-tests)
- [Monitoring](#monitoring)
- [Project Structure](#project-structure)

---

## The Big Picture

```
POST /shorten  {"url": "https://very-long-url.com"}
        ↓
Snowflake ID generated (distributed, no collisions)
        ↓
Saved to PostgreSQL
        ↓
Returns {"short_url": "http://short.ly/aB3xZ9"}

─────────────────────────────────────────────────

GET /aB3xZ9
        ↓
L1: In-process LRU cache (0ms)
        ↓ miss
L2: Redis cache (0.3ms)
        ↓ miss
L3: PostgreSQL (5ms)
        ↓
301 Redirect to original URL
        ↓
Click event → Redis Stream (async, off the hot path)
        ↓
Background aggregator → PostgreSQL analytics
```

---
