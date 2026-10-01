web: sh -c 'export AQUASENSE_MODEL_PATH="${AQUASENSE_MODEL_PATH:-$PWD/best.pt}"; python -m backend.app.preflight && exec uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"'
