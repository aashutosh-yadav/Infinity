"""
Seeds N unique short codes directly into PostgreSQL (bypassing the API --
seeding through /shorten one at a time would be slow and would pollute the
/stats counters we're trying to measure cleanly), then writes a vegeta
targets file listing each code exactly once.

Because every code is brand new and has never been requested before, an
attack run against this file guarantees every single request is a genuine
cache miss on both L1 and L2 -- true cold-path traffic straight to
Postgres, as long as total requests <= number of seeded codes (so vegeta
never has to cycle back to the start of the list and re-hit an
already-cached code).

Safe to run repeatedly across sessions without clearing old data first:
  - long_url uses a uuid4 suffix (effectively zero collision probability,
    unlike the old i+small-random-int scheme, which could collide across
    separate runs on the same day)
  - short_code inserts use ON CONFLICT DO NOTHING, so a rare collision
    against a code from an earlier run is silently skipped and
    re-generated, instead of crashing the whole seed with
    UniqueViolationError

Usage:
    python seed_cold_data.py -n 20000 -o cold_targets.txt
"""

import argparse
import asyncio
import os
import random
import string
import uuid

import asyncpg
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
ALPHABET = string.ascii_letters + string.digits
BATCH_SIZE = 2000  # keeps each INSERT's param count well under Postgres's limit


def random_code(length: int = 6) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(length))


async def insert_batch(conn: asyncpg.Connection, rows: list[tuple[str, str]]) -> list[str]:
    """
    Inserts a batch with ON CONFLICT DO NOTHING, returning only the codes
    that were actually new. Codes that collided with something already in
    the table (from this run or a previous one) are silently dropped here
    rather than crashing -- the caller tops up to the target count.
    """
    values_sql = ", ".join(
        f"(${i * 2 + 1}, ${i * 2 + 2})" for i in range(len(rows))
    )
    params = [item for pair in rows for item in pair]

    query = f"""
        INSERT INTO url_shortener (short_code, long_url)
        VALUES {values_sql}
        ON CONFLICT DO NOTHING
        RETURNING short_code
    """
    inserted = await conn.fetch(query, *params)
    return [r["short_code"] for r in inserted]


async def seed(n: int) -> list[str]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL not set -- same .env the app itself uses")

    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        inserted_codes: list[str] = []

        while len(inserted_codes) < n:
            remaining = n - len(inserted_codes)
            batch_n = min(BATCH_SIZE, remaining)

            # locally dedupe this batch's generated codes before even
            # trying to insert them -- cheap, and avoids some wasted
            # round-trips for the common case
            candidate_codes = set()
            while len(candidate_codes) < batch_n:
                candidate_codes.add(random_code())

            rows = [
                (code, f"https://example.com/cold-{uuid.uuid4()}")
                for code in candidate_codes
            ]

            newly_inserted = await insert_batch(conn, rows)
            inserted_codes.extend(newly_inserted)
            # anything NOT in newly_inserted collided with an existing row
            # and gets silently retried on the next loop iteration

        return inserted_codes
    finally:
        await conn.close()


def write_targets(codes: list[str], output: str) -> None:
    random.shuffle(codes)  # avoid any accidental ordering bias
    lines = [f"GET {BASE_URL}/{code}" for code in codes]
    with open(output, "w") as f:
        f.write("\n".join(lines) + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--count", type=int, default=20000,
                         help="Number of unique short codes to seed")
    parser.add_argument("-o", "--output", default="cold_targets.txt")
    args = parser.parse_args()

    print(f"Seeding {args.count} unique short codes directly into Postgres...")
    codes = await seed(args.count)
    print(f"Seeded {len(codes)} rows.")

    write_targets(codes, args.output)
    print(f"Wrote {len(codes)} target lines to {args.output}")

    print("\nRun the cold-path attack, e.g.:")
    print(f"  vegeta attack -targets={args.output} -rate=0 -max-workers=100 "
          f"-redirects=-1 -duration=5s | vegeta report")
    print(f"\nIMPORTANT: keep total requests <= {args.count} (control via "
          f"-duration/-rate) or vegeta will cycle back and start hitting "
          f"already-cached codes, no longer measuring a true cold path.")


if __name__ == "__main__":
    asyncio.run(main())
