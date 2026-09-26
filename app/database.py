# import os
# from dotenv import load_dotenv
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base

# load_dotenv()

# DATABASE_URL = os.getenv("DATABASE_URL")

# engine = create_engine(DATABASE_URL)

# SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Base = declarative_base()
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

# engine = create_async_engine(
#     ASYNC_DATABASE_URL,
#     pool_size=20,       # was unset (SQLAlchemy default: 5) -- explicit now
#     max_overflow=20,    # was unset (SQLAlchemy default: 10) -- explicit now
# )
engine = create_async_engine(
    ASYNC_DATABASE_URL,
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
