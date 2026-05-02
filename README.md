# 🔗 High-Performance URL Shortener

A production-inspired, read-heavy URL shortener built using **FastAPI, PostgreSQL, and Redis**, with a strong focus on **performance engineering, scalability, and system design**.

---

⚠️ This project is built as an engineering exploration, not a feature-driven product. The goal is to understand real-world system behavior through benchmarking, bottleneck analysis, and iterative optimization rather than just adding features.

---

## ✨ Features

* ⚡ High-performance redirect service (~1900 RPS under load)
* 🧠 Cache-aside Redis integration (experimentally evaluated)
* 📊 Detailed performance benchmarking using `hey`
* 🔁 Idempotent URL shortening (same URL → same short code)
* 🌐 Simple frontend for testing

---

## 🏗️ Tech Stack

* **Backend:** FastAPI (Python)
* **Database:** PostgreSQL (indexed lookups)
* **Cache:** Redis (optional, evaluated)
* **Server:** Uvicorn (multi-worker)
* **Benchmarking:** hey

---

## ⚡ Architecture

```text
Client
  ↓
FastAPI (Workers)
  ↓
Redis (Cache)
  ↓
PostgreSQL (Source of Truth)
```

---

## 🚀 Performance Highlights

| Scenario      | RPS   | Avg Latency | p99     |
| ------------- | ----- | ----------- | ------- |
| Single Worker | ~317  | ~305 ms     | ~657 ms |
| 4 Workers     | ~1919 | ~49 ms      | ~115 ms |
| Redis (Warm)  | ~1500 | ~58 ms      | ~130 ms |

---

## 📊 Key Insights

### 🔥 1. Worker Scaling > Everything

* Moving from 1 → 4 workers improved performance **~6x**
* Primary bottleneck: **worker contention, not DB**

---

### ⚠️ 2. Redis Did NOT Improve Performance (Yet)

* Redis added overhead in local setup
* PostgreSQL queries were already fast (indexed, local)
* Result: **lower throughput + slightly higher latency**

---

### 🧠 3. Caching Is Context-Dependent

> Caching does NOT always improve performance.

Redis becomes useful only when:

* DB is remote (network latency)
* DB is under heavy load
* system is distributed (multi-instance)

---

### 📉 4. System Saturation Behavior

At high concurrency (c=500):

* RPS dropped to ~983
* p99 latency exceeded ~800ms
* Cause: **queueing + CPU saturation**

---

## 🧪 Benchmarking

All tests performed using:

```bash
hey -n 5000 -c 100 -disable-redirects http://127.0.0.1:8000/{short_code}
```

---

## ⚙️ Setup

### 1. Clone repo

```bash
git clone https://github.com/aashutosh-yadav/Infinity
cd Infinity
```

### 2. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run backend

```bash
uvicorn app.main:app --workers 4 --reload
```

### 5. Open frontend

```bash
open app/frontend/index.html
```

---

## 🧠 What This Project Demonstrates

* Performance benchmarking & analysis
* Identifying real bottlenecks (not assumed ones)
* Understanding concurrency & worker scaling
* Evaluating caching strategies critically
* Thinking in terms of real-world system design

---

## 🚀 Future Improvements

* Deploy database remotely (to validate caching benefits)
* Add load balancer + multi-instance setup
* Implement analytics pipeline (click tracking)
* Introduce distributed ID generation (Snowflake)
* Add rate limiting & abuse protection

---

## 📌 Key Takeaway

> Optimization must be driven by measured bottlenecks, not assumptions.

---

## ⭐ If you found this useful

Give it a star — or fork and experiment further 🚀
