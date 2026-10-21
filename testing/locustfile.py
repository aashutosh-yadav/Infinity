"""
Locust replacement for loadtest.py.

Same idea as loadtest.py -- seed N short codes, send Zipf-weighted redirect
traffic, and report latency/throughput -- but Locust handles the concurrency,
the statistics (p50/p95/p99), and the reporting.

Usage:
    # headless, summary only
    locust -f locustfile.py --headless -u 100 -r 100 -t 15s --only-summary \
           --num-keys 20 --skew 1.2

    # with the web UI at http://localhost:8089
    locust -f locustfile.py --num-keys 20 --skew 1.2

-u  = number of simulated users (== concurrency in loadtest.py)
-r  = spawn rate (users started per second)
-t  = run duration
"""

import random

import requests
from locust import HttpUser, constant, events, task

BASE_URL = "http://127.0.0.1:8000"

# Shared across all users once seeded (populated in the test_start listener).
CODES: list[str] = []
WEIGHTS: list[float] = []


def zipf_weights(n: int, skew: float) -> list[float]:
    # weight(i) ~ 1 / (rank ^ skew). Higher skew = traffic concentrated on
    # fewer "hot" codes; skew=0 would be uniform.
    raw = [1 / ((i + 1) ** skew) for i in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


def base_url(environment) -> str:
    return environment.host or BASE_URL


@events.init_command_line_parser.add_listener
def add_custom_args(parser) -> None:
    parser.add_argument("--num-keys", type=int, default=20,
                        help="how many short codes to seed and spread traffic across")
    parser.add_argument("--skew", type=float, default=1.2,
                        help="Zipf skew: higher = traffic concentrated on fewer hot keys")


@events.test_start.add_listener
def seed_codes(environment, **kwargs) -> None:
    global CODES, WEIGHTS
    opts = environment.parsed_options
    base = base_url(environment)

    CODES = []
    with requests.Session() as session:
        for i in range(opts.num_keys):
            long_url = f"https://example.com/page-{i}-{random.randint(0, 999_999)}"
            resp = session.post(f"{base}/shorten", json={"long_url": long_url})
            resp.raise_for_status()
            CODES.append(resp.json()["short_code"])

        before = session.get(f"{base}/stats").json()

    WEIGHTS = zipf_weights(opts.num_keys, opts.skew)
    print(f"\nSeeded {opts.num_keys} codes (skew={opts.skew}).")
    print(f"Stats before run: {before}\n")


@events.test_stop.add_listener
def report_stats(environment, **kwargs) -> None:
    base = base_url(environment)
    try:
        after = requests.get(f"{base}/stats", timeout=5).json()
        print(f"\nStats after run: {after}")
    except Exception as exc:
        print(f"\nCould not fetch /stats after run: {exc}")


class RedirectUser(HttpUser):
    host = BASE_URL
    wait_time = constant(0)  # hammer as fast as possible, like loadtest.py

    @task
    def follow(self) -> None:
        code = random.choices(CODES, weights=WEIGHTS, k=1)[0]
        # don't follow the redirect -- we're measuring the app, not the target
        self.client.get(f"/{code}", allow_redirects=False, name="/{short_code}")
