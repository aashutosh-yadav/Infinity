"""
Seeds N short codes and generates a Zipf-weighted targets file for `vegeta`,
so vegeta can multi-key benchmark this app at full (Go-level) speed instead
of loadtest.py's Python/asyncio-limited throughput.

vegeta's targets file just cycles through lines in order -- it has no
built-in concept of "weight". To simulate a Zipf distribution (a few hot
keys getting most of the traffic), each short code's target line is
repeated a number of times proportional to its weight, then the whole
list is shuffled so hits aren't clustered in a predictable pattern.

Usage:
    python gen_vegeta_targets.py -k 20 --skew 1.2 -o targets.txt
"""

import argparse
import random

import httpx

BASE_URL = "http://127.0.0.1:8000"


def seed_urls(n: int) -> list[str]:
    codes = []
    with httpx.Client(timeout=10.0) as client:
        for i in range(n):
            long_url = f"https://example.com/page-{i}-{random.randint(0, 999_999)}"
            resp = client.post(f"{BASE_URL}/shorten", json={"long_url": long_url})
            resp.raise_for_status()
            codes.append(resp.json()["short_code"])
    return codes


def zipf_weights(n: int, skew: float) -> list[float]:
    raw = [1 / ((i + 1) ** skew) for i in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


def build_target_lines(codes: list[str], weights: list[float], total_lines: int) -> list[str]:
    lines = []
    for code, weight in zip(codes, weights):
        # at least 1 repeat per key so every key is reachable, even a
        # very low-weight one at high skew
        repeats = max(1, round(weight * total_lines))
        lines.extend([f"GET {BASE_URL}/{code}"] * repeats)

    random.shuffle(lines)  # avoid clustering hits to the same key back-to-back
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-k", "--num-keys", type=int, default=20)
    parser.add_argument("--skew", type=float, default=1.2,
                         help="Zipf skew: higher = traffic concentrated on fewer hot keys")
    parser.add_argument("--total-lines", type=int, default=2000,
                         help="How many target lines to generate (larger = smoother weighting)")
    parser.add_argument("-o", "--output", default="targets.txt")
    args = parser.parse_args()

    print(f"Seeding {args.num_keys} short codes...")
    codes = seed_urls(args.num_keys)
    weights = zipf_weights(args.num_keys, args.skew)

    lines = build_target_lines(codes, weights, args.total_lines)

    with open(args.output, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {len(lines)} target lines across {args.num_keys} keys to {args.output}")
    print("\nRun vegeta against it, e.g.:")
    print(f"  vegeta attack -targets={args.output} -rate=0 -max-workers=100 -duration=10s | vegeta report")
    print("\n-rate=0 means 'unlimited' -- vegeta fires as fast as it can, comparable to hey's model.")
    print("Use -rate=1000 (etc.) instead if you want a fixed sustained rate rather than max throughput.")


if __name__ == "__main__":
    main()
