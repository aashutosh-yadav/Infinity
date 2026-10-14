import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

_is_local = "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL
_connect_args = {} if _is_local else {"ssl": True}

_prefixes = ("sslmode", "channel_binding")
if any(p in ASYNC_DATABASE_URL for p in _prefixes):
    from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
    parts = urlparse(ASYNC_DATABASE_URL)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k not in _prefixes])
    ASYNC_DATABASE_URL = urlunparse(parts._replace(query=query))

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    connect_args=_connect_args,
    pool_size=8,
    max_overflow=4,
)

SessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

Base = declarative_base()
