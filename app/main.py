from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse,FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .database import SessionLocal, engine
from . import models, schemas, utils
from .redis_client import redis_client


models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS conf (has to be changed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # allow any domanin (risky)
    allow_credentials=True, # auth
    allow_methods=["*"],    # http methods
    allow_headers=["*"],    # allow headers
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#root 
@app.get("/")
def serve_frontend():
    return FileResponse("app/frontend/index.html")
    

# Create short URL
@app.post("/shorten", response_model=schemas.URLResponse)
def shorten_url(url: schemas.URLCreate, db: Session = Depends(get_db)):
    # Check if URL already exists
    # if the url alrady exits then return the same short code previously generated and dont generate new code for the smae url repetatively .
    existing_url = db.query(models.URL).filter(models.URL.long_url == url.long_url).first()
    if existing_url:
        return existing_url

    short_code = utils.generate_short_code()

    db_url = models.URL(short_code=short_code, long_url=url.long_url)
    db.add(db_url)
    db.commit()
    db.refresh(db_url)

    return db_url


# Redirect to original URL
@app.get("/{short_code}")
def redirect_url(short_code: str, db: Session = Depends(get_db)):

    # 1 Try cache (Fast path)
    try : 
        cached_url = redis_client.get(short_code)
    except:
        cached_url = None # fallback safty 

    # 2. fallback to db 
    db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()

    if not db_url:
        raise HTTPException(status_code=404, detail="URL not found")

    # 3. cache after read (lazy aching)
    try : 
        redis_client.set(short_code , db_url.long_url , ex=3600)
    except:
        pass # never let cache break you app 

    return RedirectResponse(db_url.long_url)
