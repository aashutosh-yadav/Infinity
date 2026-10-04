import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# The async SQLAlchemy engine needs an async-capable driver (asyncpg)
# instead of the sync psycopg2 one. Your .env can keep using the plain
# "postgresql://" scheme -- we rewrite it here rather than making you
# change the DATABASE_URL you already have.
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Managed Postgres providers (Neon, Render, Supabase) require SSL. Local
# dev on localhost doesn't have SSL, so only enable it for remote hosts.
_is_local = "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL
_connect_args = {} if _is_local else {"ssl": True}

# providers hand out URLs with ?sslmode=require, which asyncpg may or may
# not parse depending on version -- strip it and pass SSL explicitly instead
if "sslmode" in ASYNC_DATABASE_URL:
    from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
    parts = urlparse(ASYNC_DATABASE_URL)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k != "sslmode"])
    ASYNC_DATABASE_URL = urlunparse(parts._replace(query=query))

# engine = create_async_engine(
#     ASYNC_DATABASE_URL,
#     pool_size=20,       # was unset (SQLAlchemy default: 5) -- explicit now
#     max_overflow=20,    # was unset (SQLAlchemy default: 10) -- explicit now
# )
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    connect_args=_connect_args,
    # Postgres's max_connections defaults to 100 (confirmed via `SHOW
    # max_connections`), and EVERY worker process gets its own separate
    # pool -- these numbers multiply by worker count, they don't share.
    # With --workers 8: 8 * (pool_size + max_overflow) must stay well
    # under ~97 usable slots (100 minus a few reserved for superuser).
    # 8 * (8 + 4) = 96 -- fits, with a small safety margin.
    # The old 20/20 setting (8 * 40 = 320 possible) is what caused
    # TooManyConnectionsError under real concurrent cold-path load.
    pool_size=8,
    max_overflow=4,
)

SessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

Base = declarative_base()
