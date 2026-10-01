# OceanAid backend

Offline-first FastAPI implementation of the PRD API. It stores survey state in SQLite and keeps navigation refusal, confidence formatting, provenance, and report exports at the API boundary.

```bash
cd Main
python3 -m uvicorn backend.app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the interactive API. Upload an image, GeoTIFF, XTF, JSF, or SL2 file to `POST /v1/surveys/{id}/ingest`, then call `POST /v1/surveys/{id}/process`.

The bundled processor uses the verified `best.pt` YOLO checkpoint. Its scores are deliberately marked `calibrated: false`, and the current runtime does not fabricate physical-verifier features. It refuses coordinates without valid navigation, heading, and source-derived cross-track resolution. If the model is unavailable or an inference batch fails, processing emits `processing.failed` rather than fabricating contacts or silently returning an empty result.

## XTF extraction

`.xtf` uploads use `pyxtf` to extract both side-scan channels, build a normalized port/starboard waterfall PNG, and preserve per-ping timestamps, position, altitude, depth, heading, pitch, roll, heave, and speed. The extraction is available at `GET /v1/surveys/{id}/sonar`; the PNG is served by `GET /v1/surveys/{id}/waterfall.png`.

Only finite WGS-84 coordinate pairs inside valid latitude/longitude bounds become `GPS_FIX` records. Missing or zeroed vendor navigation stays unavailable and continues through the existing refusal path.

## JSF and SL2 extraction

JSF ingestion supports EdgeTech message-type 80 side-scan records with uncompressed envelope or analytic samples. Legacy/compressed message types are rejected with a clear error because decoding them without the vendor decompressor would be unreliable.

SL2 ingestion supports the publicly documented Lowrance format-2 frame layout and its left/right side-scan channels. The binary format varies by device firmware; malformed or unsupported frame boundaries are rejected. Both parsers write the same waterfall, QC, and per-ping navigation contract as XTF and never emit coordinates unless their source validity flag and WGS-84 bounds both pass.

## Live processing stream

`POST /v1/surveys/{id}/process` starts processing asynchronously and returns `202 Accepted`. A second request for the same survey receives `409 Conflict` while the first job is active. Subscribe first or immediately afterwards at `WS /v1/surveys/{id}/stream`. The stream emits `processing.started`, `processing.stage`, one `detection.verified` event per candidate, then a terminal `processing.complete` or `processing.failed` event. `GET /v1/surveys/{id}/processing` returns the latest status persisted in SQLite for reconnecting clients.

Reprocessing replaces the active detection set. Reviews attached to the previous run are archived first and remain available at `GET /v1/surveys/{id}/review-history` and in the JSON report, so audit decisions are not silently discarded.

`GET /health` is a readiness check: it returns `200` only when the configured model loads, and `503` with `status: degraded` when inference is unavailable.

For shared hosted deployments, set `OCEANAID_API_KEY`. Operational HTTP routes then require `X-API-Key` (or the `api_key` query parameter for browser-loaded artifacts), and survey WebSockets require the same value as `api_key`. Leave it unset for local/offline operation.

Run tests from `Main`:

```bash
PYTHONPATH=backend pytest backend/tests -q
```
