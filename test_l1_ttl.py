"""
Proves L1's TTL expiry behavior with actual evidence, not assumption.

MUST be run against a server started with --workers 1 -- with multiple
workers, each has its own separate L1 cache and /stats counters, and a
request could land on any of them, making the result meaningless.

Sequence:
  1. Create a short URL (fresh code, nothing cached yet)
  2. Hit it once -> should be a DB hit (first-ever request for this code),
     which also populates L1 and L2
  3. Hit it again immediately -> should be an L1 hit (still warm)
  4. Wait past L1's TTL (60s) but well under L2's (3600s)
  5. Hit it again -> should now be an L2 hit (L1 expired and let go of it,
     but Redis still has it) -- and this request should re-populate L1
  6. Hit it one more time immediately -> should be an L1 hit again,
     proving the re-population in step 5 actually worked

Usage:
    python test_l1_ttl.py
"""

import time
import httpx

BASE_URL = "http://127.0.0.1:8000"
L1_TTL_SECONDS = 60
WAIT_BUFFER = 5  # extra margin past the TTL, so we're not racing the clock


def get_stats(client: httpx.Client) -> dict:
    return client.get(f"{BASE_URL}/stats").json()


def hit(client: httpx.Client, short_code: str) -> None:
    client.get(f"{BASE_URL}/{short_code}", follow_redirects=False)


def diff(before: dict, after: dict) -> dict:
    return {
        "l1_hits": after["l1_hits"] - before["l1_hits"],
        "l2_hits": after["l2_hits"] - before["l2_hits"],
        "db_hits": after["db_hits"] - before["db_hits"],
    }


def main() -> None:
    with httpx.Client(timeout=10.0) as client:
        # Step 1: create a fresh short URL, guaranteed never hit before
        resp = client.post(f"{BASE_URL}/shorten", json={
            "long_url": f"https://example.com/ttl-test-{time.time()}"
        })
        short_code = resp.json()["short_code"]
        print(f"Created fresh short code: {short_code}\n")

        # Step 2: first-ever hit -> should be a DB hit
        before = get_stats(client)
        hit(client, short_code)
        after = get_stats(client)
        print("Step 2 (first request, should be DB hit):", diff(before, after))

        # Step 3: immediate second hit -> should be an L1 hit
        before = get_stats(client)
        hit(client, short_code)
        after = get_stats(client)
        print("Step 3 (immediate re-hit, should be L1 hit):", diff(before, after))

        # Step 4: wait past L1's TTL
        wait_time = L1_TTL_SECONDS + WAIT_BUFFER
        print(f"\nWaiting {wait_time}s for L1 entry to expire "
              f"(L1 TTL = {L1_TTL_SECONDS}s)...")
        time.sleep(wait_time)

        # Step 5: hit after L1 expiry -> should be an L2 hit (Redis still
        # has it, TTL=3600s), and this should re-populate L1
        before = get_stats(client)
        hit(client, short_code)
        after = get_stats(client)
        print("\nStep 5 (after L1 TTL expiry, should be L2 hit):", diff(before, after))

        # Step 6: immediate hit again -> should be L1 hit, proving step 5
        # actually re-populated L1
        before = get_stats(client)
        hit(client, short_code)
        after = get_stats(client)
        print("Step 6 (immediate re-hit, should be L1 hit again -- "
              "proves re-population worked):", diff(before, after))

        print("\nDone. Expected pattern: db_hits=1 at step 2, l1_hits=1 at "
              "steps 3 and 6, l2_hits=1 at step 5, and nothing unexpected "
              "showing up anywhere else.")


if __name__ == "__main__":
    main()
