# """
# Multi-key load tester with a power-law (Zipf) key distribution.

# `hey` only hits one URL per run, which is why every benchmark so far has
# hammered a single short code (ly1G6y) -- fine for isolating raw throughput,
# but overly optimistic for cache hit rates, since real traffic spreads
# across many links, not one. This script:

#   1. Seeds N short codes via POST /shorten
#   2. Assigns each one a weight following a Zipf distribution (a small
#      number of "hot" codes get most of the traffic, a long tail gets
#      little) -- a reasonable stand-in for real URL-shortener traffic
#   3. Fires concurrent requests at those codes according to that
#      distribution
#   4. Reports throughput/latency (same shape as hey's summary) plus
#      /stats before and after, so you can see actual cache hit rates
#      under a realistic access pattern.

# Usage:
#     python loadtest.py -n 5000 -c 100 -k 20 --skew 1.2
# """

# import asyncio
# import argparse
# import random
# import time

# import httpx

# BASE_URL = "http://127.0.0.1:8000"


# async def seed_urls(client: httpx.AsyncClient, n: int) -> list[str]:
#     codes = []
#     for i in range(n):
#         long_url = f"https://example.com/page-{i}-{random.randint(0, 999_999)}"
#         resp = await client.post(f"{BASE_URL}/shorten", json={"long_url": long_url})
#         resp.raise_for_status()
#         codes.append(resp.json()["short_code"])
#     return codes


# def zipf_weights(n: int, skew: float) -> list[float]:
#     # rank-based Zipf: weight(i) ~ 1 / (rank ^ skew). Higher skew = traffic
#     # concentrated on fewer "hot" codes; skew=0 would be uniform random.
#     raw = [1 / ((i + 1) ** skew) for i in range(n)]
#     total = sum(raw)
#     return [w / total for w in raw]


# async def worker(client: httpx.AsyncClient, codes: list[str], weights: list[float],
#                   n_requests: int, latencies: list[float], errors: list[int]) -> None:
#     for _ in range(n_requests):
#         code = random.choices(codes, weights=weights, k=1)[0]
#         start = time.perf_counter()
#         try:
#             resp = await client.get(f"{BASE_URL}/{code}", follow_redirects=False)
#             if resp.status_code not in (302, 307):
#                 errors[0] += 1
#         except Exception:
#             errors[0] += 1
#         latencies.append(time.perf_counter() - start)


# async def get_stats(client: httpx.AsyncClient) -> dict | None:
#     try:
#         resp = await client.get(f"{BASE_URL}/stats")
#         return resp.json()
#     except Exception:
#         return None


# def percentile(sorted_vals: list[float], p: float) -> float:
#     if not sorted_vals:
#         return 0.0
#     idx = min(int(len(sorted_vals) * p), len(sorted_vals) - 1)
#     return sorted_vals[idx] * 1000  # ms


# async def main() -> None:
#     parser = argparse.ArgumentParser(description=__doc__)
#     parser.add_argument("-n", "--num-requests", type=int, default=5000)
#     parser.add_argument("-c", "--concurrency", type=int, default=100)
#     parser.add_argument("-k", "--num-keys", type=int, default=20)
#     parser.add_argument("--skew", type=float, default=1.2,
#                          help="Zipf skew: higher = traffic concentrated on fewer hot keys")
#     args = parser.parse_args()

#     # async with httpx.AsyncClient(timeout=10.0) as client:
#     limits = httpx.Limits(max_keepalive_connections=200, max_connections=200)
#     async with httpx.AsyncClient(timeout=10.0, limits=limits) as client:
#         print(f"Seeding {args.num_keys} short codes...")
#         codes = await seed_urls(client, args.num_keys)
#         weights = zipf_weights(args.num_keys, args.skew)

#         before = await get_stats(client)
#         print(f"Stats before run: {before}")

#         requests_per_worker = args.num_requests // args.concurrency
#         total_sent = requests_per_worker * args.concurrency
#         latencies: list[float] = []
#         errors = [0]

#         start = time.perf_counter()
#         await asyncio.gather(*[
#             worker(client, codes, weights, requests_per_worker, latencies, errors)
#             for _ in range(args.concurrency)
#         ])
#         total_time = time.perf_counter() - start

#         latencies.sort()
#         n = len(latencies)

#         print("\n=== Results ===")
#         print(f"Total requests: {total_sent}")
#         print(f"Concurrency:    {args.concurrency}")
#         print(f"Num keys:       {args.num_keys} (zipf skew={args.skew})")
#         print(f"Total time:     {total_time:.4f} sec")
#         print(f"Requests/sec:   {total_sent / total_time:.2f}")
#         print(f"Errors:         {errors[0]}")
#         if n:
#             print(f"Avg latency:    {sum(latencies) / n * 1000:.2f} ms")
#             print(f"p50:            {percentile(latencies, 0.50):.2f} ms")
#             print(f"p95:            {percentile(latencies, 0.95):.2f} ms")
#             print(f"p99:            {percentile(latencies, 0.99):.2f} ms")

#         after = await get_stats(client)
#         print(f"\nStats after run: {after}")


# if __name__ == "__main__":
#     asyncio.run(main())
"""
Multi-key load tester with a power-law (Zipf) key distribution.

`hey` only hits one URL per run, which is why every benchmark so far has
hammered a single short code (ly1G6y) -- fine for isolating raw throughput,
but overly optimistic for cache hit rates, since real traffic spreads
across many links, not one. This script:

  1. Seeds N short codes via POST /shorten
  2. Assigns each one a weight following a Zipf distribution (a small
     number of "hot" codes get most of the traffic, a long tail gets
     little) -- a reasonable stand-in for real URL-shortener traffic
  3. Fires concurrent requests at those codes according to that
     distribution
  4. Reports throughput/latency (same shape as hey's summary) plus
     /stats before and after, so you can see actual cache hit rates
     under a realistic access pattern.

Usage:
    python loadtest.py -n 5000 -c 100 -k 20 --skew 1.2
"""

import asyncio
import argparse
import random
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"


async def seed_urls(client: httpx.AsyncClient, n: int) -> list[str]:
    codes = []
    for i in range(n):
        long_url = f"https://example.com/page-{i}-{random.randint(0, 999_999)}"
        resp = await client.post(f"{BASE_URL}/shorten", json={"long_url": long_url})
        resp.raise_for_status()
        codes.append(resp.json()["short_code"])
    return codes


def zipf_weights(n: int, skew: float) -> list[float]:
    # rank-based Zipf: weight(i) ~ 1 / (rank ^ skew). Higher skew = traffic
    # concentrated on fewer "hot" codes; skew=0 would be uniform random.
    raw = [1 / ((i + 1) ** skew) for i in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


async def worker(codes: list[str], weights: list[float], n_requests: int,
                  latencies: list[float], errors: list[int]) -> None:
    # Each worker gets its OWN client/connection pool now, instead of all
    # 100 workers sharing one. Testing whether the shared pool's internal
    # locking (httpx/httpcore manage connection checkout with async locks)
    # was serializing requests under high concurrency.
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=5)
    async with httpx.AsyncClient(timeout=10.0, limits=limits) as client:
        for _ in range(n_requests):
            code = random.choices(codes, weights=weights, k=1)[0]
            start = time.perf_counter()
            try:
                resp = await client.get(f"{BASE_URL}/{code}", follow_redirects=False)
                if resp.status_code not in (302, 307):
                    errors[0] += 1
            except Exception:
                errors[0] += 1
            latencies.append(time.perf_counter() - start)


async def get_stats(client: httpx.AsyncClient) -> dict | None:
    try:
        resp = await client.get(f"{BASE_URL}/stats")
        return resp.json()
    except Exception:
        return None


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(int(len(sorted_vals) * p), len(sorted_vals) - 1)
    return sorted_vals[idx] * 1000  # ms


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--num-requests", type=int, default=5000)
    parser.add_argument("-c", "--concurrency", type=int, default=100)
    parser.add_argument("-k", "--num-keys", type=int, default=20)
    parser.add_argument("--skew", type=float, default=1.2,
                         help="Zipf skew: higher = traffic concentrated on fewer hot keys")
    args = parser.parse_args()

    # Separate client just for setup (seeding codes) and before/after stats --
    # this one being shared is fine, since it's not under concurrent load.
    async with httpx.AsyncClient(timeout=10.0) as setup_client:
        print(f"Seeding {args.num_keys} short codes...")
        codes = await seed_urls(setup_client, args.num_keys)
        weights = zipf_weights(args.num_keys, args.skew)

        before = await get_stats(setup_client)
        print(f"Stats before run: {before}")

        requests_per_worker = args.num_requests // args.concurrency
        total_sent = requests_per_worker * args.concurrency
        latencies: list[float] = []
        errors = [0]

        start = time.perf_counter()
        await asyncio.gather(*[
            worker(codes, weights, requests_per_worker, latencies, errors)
            for _ in range(args.concurrency)
        ])
        total_time = time.perf_counter() - start

        latencies.sort()
        n = len(latencies)

        print("\n=== Results ===")
        print(f"Total requests: {total_sent}")
        print(f"Concurrency:    {args.concurrency}")
        print(f"Num keys:       {args.num_keys} (zipf skew={args.skew})")
        print(f"Total time:     {total_time:.4f} sec")
        print(f"Requests/sec:   {total_sent / total_time:.2f}")
        print(f"Errors:         {errors[0]}")
        if n:
            print(f"Avg latency:    {sum(latencies) / n * 1000:.2f} ms")
            print(f"p50:            {percentile(latencies, 0.50):.2f} ms")
            print(f"p95:            {percentile(latencies, 0.95):.2f} ms")
            print(f"p99:            {percentile(latencies, 0.99):.2f} ms")

        after = await get_stats(setup_client)
        print(f"\nStats after run: {after}")


if __name__ == "__main__":
    asyncio.run(main())
