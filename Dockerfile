FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AQUASENSE_DATA_DIR=/data \
    AQUASENSE_MODEL_PATH=/data/models/best.pt \
    AQUASENSE_MODEL_SHA256=342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app /app/app
COPY best.pt /data/models/best.pt

RUN mkdir -p /data/uploads /data/artifacts /data/models
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Production must never start with a missing, corrupt, or incompatible model.
CMD ["sh", "-c", "python -m app.preflight && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
