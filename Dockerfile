FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AQUASENSE_DATA_DIR=/data \
    AQUASENSE_MODEL_PATH=/data/models/best.pt \
    PORT=8000

# Minimal system libraries for imaging, fonts, inference, and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache dependencies
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and install the committed checkpoint at its runtime path.
COPY backend/app /app/app
COPY best.pt /data/models/best.pt

RUN mkdir -p /data/uploads /data/artifacts /data/models
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
