FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AQUASENSE_DATA_DIR=/data \
    AQUASENSE_MODEL_PATH=/data/models/best.pt \
    AQUASENSE_MODEL_SHA256=342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53 \
    AQUASENSE_DEVICE=cpu \
    AQUASENSE_BATCH_SIZE=1 \
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
# Keep the immutable seed outside /data because Render mounts its persistent
# disk over /data at runtime, hiding files baked into that image path.
COPY best.pt /app/model-seed/best.pt

RUN mkdir -p /data/uploads /data/artifacts /data/models
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Seed the mounted disk, verify the model, and only then serve traffic.
CMD ["sh", "-c", "mkdir -p /data/uploads /data/artifacts /data/models && cp -f /app/model-seed/best.pt /data/models/best.pt && python -m app.preflight && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
