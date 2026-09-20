# import redis

# redis_client = redis.Redis(
#     host="localhost",
#     port=6379,
#     db=0,
#     decode_responses=True,
#     socket_connect_timeout=2  # avoid hanging
# )
import redis.asyncio as redis

# async client: reads/writes are now `await`-able and never block the
# event loop, unlike the old sync `redis` client.
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True,
    socket_connect_timeout=2  # avoid hanging
)
