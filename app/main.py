# from fastapi import FastAPI, Depends, HTTPException
# from sqlalchemy.orm import Session
# from fastapi.responses import RedirectResponse,FileResponse
# from fastapi.middleware.cors import CORSMiddleware

# from .database import SessionLocal, engine
# from . import models, schemas, utils
# from .redis_client import redis_client


# models.Base.metadata.create_all(bind=engine)

# app = FastAPI()

# # CORS conf (has to be changed)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],    # allow any domanin (risky)
#     allow_credentials=True, # auth
#     allow_methods=["*"],    # http methods
#     allow_headers=["*"],    # allow headers
# )

# # Dependency
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# #root
# @app.get("/")
# def serve_frontend():
#     return FileResponse("app/frontend/index.html")


# # Create short URL
# @app.post("/shorten", response_model=schemas.URLResponse)
# def shorten_url(url: schemas.URLCreate, db: Session = Depends(get_db)):
#     # Check if URL already exists
#     # if the url alrady exits then return the same short code previously generated and dont generate new code for the smae url repetatively .
#     existing_url = db.query(models.URL).filter(models.URL.long_url == url.long_url).first()
#     if existing_url:
#         return existing_url

#     short_code = utils.generate_short_code()

#     db_url = models.URL(short_code=short_code, long_url=url.long_url)
#     db.add(db_url)
#     db.commit()
#     db.refresh(db_url)

#     return db_url


# # Redirect to original URL
# @app.get("/{short_code}")
# def redirect_url(short_code: str, db: Session = Depends(get_db)):

#     # 1. Try cache (fast path)
#     try:
#         cached_url = redis_client.get(short_code)
#     except:
#         cached_url = None  # fallback safety

#     if cached_url:
#         return RedirectResponse(cached_url)

#     # 2. Cache miss -> fallback to db
#     db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()

#     if not db_url:
#         raise HTTPException(status_code=404, detail="URL not found")

#     # 3. Cache after read (lazy caching)
#     try:
#         redis_client.set(short_code, db_url.long_url, ex=3600)
#     except:
#         pass  # never let cache break your app

#     return RedirectResponse(db_url.long_url)
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .database import SessionLocal, engine, Base
from . import models, schemas, utils
from .redis_client import redis_client
from .l1_cache import LRUCache

from .stats import stats
# L1 cache: in-process, checked before Redis (L2). TTL kept shorter than
# Redis's so a change made elsewhere doesn't stay stale in-process for too
# long -- L1 is meant to be a thin, fast skim off the top, not the source
# of truth for freshness.
l1_cache = LRUCache(max_size=1024, ttl_seconds=60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # replaces the old sync `models.Base.metadata.create_all(bind=engine)`
    # -- the async engine needs this run inside an async connection.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)

# CORS conf (has to be changed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # allow any domanin (risky)
    allow_credentials=True, # auth
    allow_methods=["*"],    # http methods
    allow_headers=["*"],    # allow headers
)


# Dependency
async def get_db():
    async with SessionLocal() as db:
        yield db


# root
@app.get("/")
def serve_frontend():
    return FileResponse("app/frontend/index.html")

# Cache hit-rate visibility. NOTE: with multiple workers, this only
# reflects the one worker process that handles this request -- see the
# caveat in stats.py.
@app.get("/stats")
def get_stats():
    return stats.as_dict()

# Create short URL
@app.post("/shorten", response_model=schemas.URLResponse)
async def shorten_url(url: schemas.URLCreate, db: AsyncSession = Depends(get_db)):
    # Check if URL already exists
    # if the url alrady exits then return the same short code previously generated and dont generate new code for the smae url repetatively .
    result = await db.execute(select(models.URL).where(models.URL.long_url == url.long_url))
    existing_url = result.scalar_one_or_none()
    if existing_url:
        return existing_url

    short_code = utils.generate_short_code()

    db_url = models.URL(short_code=short_code, long_url=url.long_url)
    db.add(db_url)
    await db.commit()
    await db.refresh(db_url)

    return db_url


# Redirect to original URL
# @app.get("/{short_code}")
# async def redirect_url(short_code: str, db: AsyncSession = Depends(get_db)):

#     # 1. Try L1 (in-process) cache first -- no network hop at all
#     l1_hit = await l1_cache.get(short_code)
#     if l1_hit:
#         return RedirectResponse(l1_hit)

#     # 2. Try L2 (Redis) cache
#     try:
#         cached_url = await redis_client.get(short_code)
#     except Exception:
#         cached_url = None  # fallback safety -- never let cache being down break the app

#     if cached_url:
#         await l1_cache.set(short_code, cached_url)  # promote into L1 for next time
#         return RedirectResponse(cached_url)

#     # 3. Cache miss on both levels -> fallback to db
#     result = await db.execute(select(models.URL).where(models.URL.short_code == short_code))
#     db_url = result.scalar_one_or_none()

#     if not db_url:
#         raise HTTPException(status_code=404, detail="URL not found")

#     # 4. Populate both cache levels (lazy caching)
#     try:
#         await redis_client.set(short_code, db_url.long_url, ex=3600)
#     except Exception:
#         pass  # never let cache break your app
#     await l1_cache.set(short_code, db_url.long_url)

#     return RedirectResponse(db_url.long_url)
@app.get("/{short_code}")
async def redirect_url(short_code: str, db: AsyncSession = Depends(get_db)):

    # 1. Try L1 (in-process) cache first -- no network hop at all
    l1_hit = await l1_cache.get(short_code)
    if l1_hit:
        stats.l1_hits += 1
        return RedirectResponse(l1_hit)

    # 2. Try L2 (Redis) cache
    try:
        cached_url = await redis_client.get(short_code)
    except Exception:
        cached_url = None  # fallback safety -- never let cache being down break the app

    if cached_url:
        stats.l2_hits += 1
        await l1_cache.set(short_code, cached_url)  # promote into L1 for next time
        return RedirectResponse(cached_url)

    # 3. Cache miss on both levels -> fallback to db
    result = await db.execute(select(models.URL).where(models.URL.short_code == short_code))
    db_url = result.scalar_one_or_none()

    if not db_url:
        stats.misses += 1
        raise HTTPException(status_code=404, detail="URL not found")

    stats.db_hits += 1

    # 4. Populate both cache levels (lazy caching)
    try:
        await redis_client.set(short_code, db_url.long_url, ex=3600)
    except Exception:
        pass  # never let cache break your app
    await l1_cache.set(short_code, db_url.long_url)

    return RedirectResponse(db_url.long_url)
