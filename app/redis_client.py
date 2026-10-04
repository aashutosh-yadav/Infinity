import os

import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

# Configurable via env so the same code works locally and deployed.
# Local default: REDIS_URL unset -> plain localhost.
# Deployed: set REDIS_URL to the managed Redis connection string, e.g.
#   rediss://:password@host.upstash.io:6379   (Upstash / TLS)
# async client: reads/writes are `await`-able and never block the event loop.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,  # avoid hanging
)
