# AquaSense backend

Offline-first FastAPI implementation of the PRD API. It stores survey state in SQLite and keeps navigation refusal, confidence formatting, provenance, and report exports at the API boundary.

```bash
cd Main
python3 -m uvicorn backend.app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the interactive API. Upload an image, GeoTIFF, XTF, JSF, or SL2 file to `POST /v1/surveys/{id}/ingest`, then call `POST /v1/surveys/{id}/process`.

The bundled processor is deliberately an **uncalibrated heuristic baseline**, not a trained YOLO model. It marks all resulting detections as `calibrated: false` and refuses coordinates without parsed navigation metadata. Replace `run_pipeline` with the trained detector adapter only after evaluation and Platt calibration are available.

## XTF extraction

`.xtf` uploads use `pyxtf` to extract both side-scan channels, build a normalized port/starboard waterfall PNG, and preserve per-ping timestamps, position, altitude, depth, heading, pitch, roll, heave, and speed. The extraction is available at `GET /v1/surveys/{id}/sonar`; the PNG is served by `GET /v1/surveys/{id}/waterfall.png`.

Only finite WGS-84 coordinate pairs inside valid latitude/longitude bounds become `GPS_FIX` records. Missing or zeroed vendor navigation stays unavailable and continues through the existing refusal path.

## JSF and SL2 extraction

JSF ingestion supports EdgeTech message-type 80 side-scan records with uncompressed envelope or analytic samples. Legacy/compressed message types are rejected with a clear error because decoding them without the vendor decompressor would be unreliable.

SL2 ingestion supports the publicly documented Lowrance format-2 frame layout and its left/right side-scan channels. The binary format varies by device firmware; malformed or unsupported frame boundaries are rejected. Both parsers write the same waterfall, QC, and per-ping navigation contract as XTF and never emit coordinates unless their source validity flag and WGS-84 bounds both pass.

## Live processing stream

`POST /v1/surveys/{id}/process` starts processing asynchronously and returns `202 Accepted`. Subscribe first or immediately afterwards at `WS /v1/surveys/{id}/stream`. The stream emits `processing.started`, `processing.stage`, one `detection.verified` event per cleared candidate, then a terminal `processing.complete` or `processing.failed` event. `GET /v1/surveys/{id}/processing` returns the latest stage for reconnecting clients.

Run tests from `Main`:

```bash
PYTHONPATH=backend pytest backend/tests -q
```
