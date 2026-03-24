from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse, HTMLResponse

from .database import SessionLocal, engine
from . import models, schemas, utils
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

models.Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open("frontend/index.html") as f:
        return f.read()

# Create short URL
@app.post("/shorten", response_model=schemas.URLResponse)
def shorten_url(url: schemas.URLCreate, db: Session = Depends(get_db)):
    short_code = utils.generate_short_code()

    db_url = models.URL(short_code=short_code, long_url=url.long_url)
    db.add(db_url)
    db.commit()
    db.refresh(db_url)

    return db_url


# Redirect to original URL
@app.get("/{short_code}")
def redirect_url(short_code: str, db: Session = Depends(get_db)):
    db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()

    if not db_url:
        raise HTTPException(status_code=404, detail="URL not found")

    return RedirectResponse(db_url.long_url)