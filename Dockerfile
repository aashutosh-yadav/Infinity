FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1

# Render/Railway/Fly inject $PORT; default to 8000 locally.
# Free tiers have ~512MB RAM: 2 workers is the ceiling, not 8.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
