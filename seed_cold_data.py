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

Usage:
    python seed_cold_data.py -n 20000 -o cold_targets.txt
"""

import argparse
import asyncio
import os
import random
import string

import asyncpg
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
ALPHABET = string.ascii_letters + string.digits


def random_code(length: int = 6) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(length))


async def seed(n: int) -> list[str]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL not set -- same .env the app itself uses")

    # asyncpg wants the bare postgresql:// scheme, not the +asyncpg
    # SQLAlchemy variant -- this connects directly, no SQLAlchemy involved.
    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        codes = set()
        while len(codes) < n:
            codes.add(random_code())
        codes = list(codes)

        rows = [(code, f"https://example.com/cold-{i}-{random.randint(0, 999_999)}")
                 for i, code in enumerate(codes)]

        # executemany via a prepared statement -- fast bulk insert, much
        # faster than N individual HTTP round-trips through /shorten
        await conn.executemany(
            "INSERT INTO url_shortener (short_code, long_url) VALUES ($1, $2)",
            rows
        )
        return codes
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
