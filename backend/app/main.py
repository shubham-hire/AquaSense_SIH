from __future__ import annotations

import csv
import asyncio
import io
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .pipeline import SUPPORTED_FORMATS, inspect_file, iter_pipeline
from .repository import Repository
from .schemas import Detection
from .streaming import event_hub

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("AQUASENSE_DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
ARTIFACT_DIR = DATA_DIR / "artifacts"
repository = Repository(DATA_DIR / "aquasense.sqlite3")

app = FastAPI(title="AquaSense API", version="0.1.0", description="Offline-first sonar survey processing API")
default_origins = "http://localhost:3000,http://127.0.0.1:3000"
cors_origins = [origin.strip() for origin in os.getenv("AQUASENSE_CORS_ORIGINS", default_origins).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["*"], allow_headers=["*"])


def get_detection(detection_id: str) -> dict:
    detection = repository.detection(detection_id)
    if not detection:
        raise HTTPException(404, "Detection not found")
    return detection


def survey_detections(survey_id: str) -> list[dict]:
    if not repository.ingest_info(survey_id):
        raise HTTPException(404, "Survey has not been ingested")
    return repository.detections_for_survey(survey_id)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "aquasense-api", "storage": "sqlite"}


@app.post("/v1/surveys/{survey_id}/ingest")
async def ingest_survey(survey_id: str, file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(415, f"Supported formats: {', '.join(SUPPORTED_FORMATS)}")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / f"{survey_id}-{uuid4()}{suffix}"
    size = 0
    with destination.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > 500 * 1024 * 1024:
                destination.unlink(missing_ok=True)
                raise HTTPException(413, "Upload exceeds the 500 MB offline processing limit")
            output.write(chunk)
    try:
        qc, extraction = inspect_file(survey_id, destination, file.filename or destination.name, ARTIFACT_DIR / f"{survey_id}-{uuid4()}")
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    repository.save_ingest(survey_id, str(destination), qc.model_dump(mode="json"), extraction)
    return {"survey_id": survey_id, "qc_report": qc, "xtf_extraction": {"ping_count": extraction["ping_count"], "valid_navigation_pings": extraction["valid_navigation_pings"], "waterfall_shape": extraction["waterfall_shape"]} if extraction else None}


async def _process_in_background(survey_id: str, source_path: str, qc: dict, extraction: dict | None, dsp_applied: bool) -> None:
    try:
        await event_hub.publish(survey_id, "processing.started")
        await event_hub.publish(survey_id, "processing.stage", stage="detection", progress_percent=25)
        detections = []
        # The iterator is the model-integration contract: each candidate can be
        # verified and published without waiting for the full mission.
        for number, detection in enumerate(iter_pipeline(survey_id, Path(source_path), qc, dsp_applied, extraction), start=1):
            detections.append(detection)
            await event_hub.publish(survey_id, "processing.stage", stage="verification", progress_percent=75)
            await event_hub.publish(survey_id, "detection.verified", data=detection, sequence=number)
            await asyncio.sleep(0)  # allow maps/queues to redraw between candidates
        repository.replace_detections(survey_id, detections)
        await event_hub.publish(survey_id, "processing.complete", detection_count=len(detections), progress_percent=100)
    except Exception as exc:  # clients get a terminal state rather than a silent disconnect
        await event_hub.publish(survey_id, "processing.failed", detail=str(exc))


@app.post("/v1/surveys/{survey_id}/process", status_code=202)
async def process_survey(survey_id: str, dsp_applied: bool = False) -> dict:
    info = repository.ingest_info(survey_id)
    if not info:
        raise HTTPException(409, "Ingest a survey before processing it")
    source_path, qc, extraction = info
    asyncio.create_task(_process_in_background(survey_id, source_path, qc, extraction, dsp_applied))
    return {"survey_id": survey_id, "status": "processing_started", "stream_url": f"/v1/surveys/{survey_id}/stream"}


@app.get("/v1/surveys/{survey_id}/processing")
def processing_status(survey_id: str) -> dict:
    return event_hub._state.get(survey_id, {"event": "stream.ready", "survey_id": survey_id})


@app.get("/v1/surveys/{survey_id}/detections", response_model=list[Detection])
def list_detections(survey_id: str) -> list[dict]:
    return survey_detections(survey_id)


@app.get("/v1/surveys/{survey_id}/sonar")
def sonar_metadata(survey_id: str) -> dict:
    info = repository.ingest_info(survey_id)
    if not info or not info[2]:
        raise HTTPException(404, "No extracted XTF sonar payload is available for this survey")
    extraction = info[2]
    return {key: value for key, value in extraction.items() if key not in {"waterfall_path", "metadata_path"}}


@app.get("/v1/surveys/{survey_id}/waterfall.png")
def waterfall_image(survey_id: str) -> Response:
    info = repository.ingest_info(survey_id)
    if not info or not info[2] or not Path(info[2]["waterfall_path"]).is_file():
        raise HTTPException(404, "No extracted XTF waterfall image is available for this survey")
    return Response(Path(info[2]["waterfall_path"]).read_bytes(), media_type="image/png")


@app.get("/v1/detections/{detection_id}", response_model=Detection)
def detection_detail(detection_id: str) -> dict:
    return get_detection(detection_id)


@app.get("/v1/detections/{detection_id}/explain")
def explain_detection(detection_id: str) -> dict:
    item = get_detection(detection_id)
    return {"detection_id": item["id"], "verification_features": item["verification_features"], "feature_weights": item["feature_weights"], "calibrated": item["calibrated"], "model_version": item["model_version"]}


@app.get("/v1/surveys/{survey_id}/report.json")
def json_report(survey_id: str) -> Response:
    items = survey_detections(survey_id)
    payload = {"report_metadata": {"survey_id": survey_id, "total_detections": len(items), "unlocated_refusal_count": sum(d["position"]["position_source"] == "UNAVAILABLE" for d in items)}, "detections": items}
    return Response(json.dumps(payload, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{survey_id}-report.json"'})


@app.get("/v1/surveys/{survey_id}/report.csv")
def csv_report(survey_id: str) -> Response:
    items = survey_detections(survey_id)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["detection_id", "latitude", "longitude", "classification", "confidence_percent", "width_m", "height_m", "position_source", "low_data_quality", "calibrated", "survey_id", "ping_timestamp"])
    writer.writeheader()
    for d in items:
        writer.writerow({"detection_id": d["id"], "latitude": d["position"]["latitude"], "longitude": d["position"]["longitude"], "classification": d["classification"], "confidence_percent": d["confidence_percent"], "width_m": d["bounding_box"]["width_m"], "height_m": d["bounding_box"]["height_m"], "position_source": d["position"]["position_source"], "low_data_quality": d["low_data_quality"], "calibrated": d["calibrated"], "survey_id": survey_id, "ping_timestamp": d["ping_timestamp"]})
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{survey_id}-report.csv"'})


@app.get("/v1/surveys/{survey_id}/geojson")
def geojson_report(survey_id: str) -> dict:
    items = survey_detections(survey_id)
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [d["position"]["longitude"], d["position"]["latitude"]]}, "properties": {"id": d["id"], "classification": d["classification"], "confidence_percent": d["confidence_percent"], "width_m": d["bounding_box"]["width_m"], "height_m": d["bounding_box"]["height_m"]}} for d in items if d["position"]["position_source"] == "GPS_FIX"]
    return {"type": "FeatureCollection", "name": f"AquaSense_{survey_id}_hazards", "features": features}


@app.get("/v1/surveys/{survey_id}/report.pdf")
def pdf_report(survey_id: str) -> Response:
    items = survey_detections(survey_id)
    pdf = io.BytesIO(); page = canvas.Canvas(pdf, pagesize=letter)
    page.setTitle(f"AquaSense mission report — {survey_id}"); page.drawString(72, 750, f"AquaSense mission report: {survey_id}")
    page.drawString(72, 730, f"Detections: {len(items)} | Unlocated: {sum(d['position']['position_source'] == 'UNAVAILABLE' for d in items)}")
    y = 700
    for d in items:
        page.drawString(72, y, f"{d['id'][:8]}  {d['classification']}  {d['confidence_percent']}%  {d['position']['position_source']}"); y -= 20
        if y < 70: page.showPage(); y = 750
    page.save()
    return Response(pdf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{survey_id}-report.pdf"'})


@app.websocket("/v1/surveys/{survey_id}/stream")
async def stream_detections(websocket: WebSocket, survey_id: str) -> None:
    await websocket.accept()
    queue = event_hub.subscribe(survey_id)
    try:
        # Late subscribers get persisted events after a completed run. During an
        # active run they receive each event as verification clears it.
        state = event_hub._state.get(survey_id, {})
        if state.get("event") == "processing.complete":
            for detection in repository.detections_for_survey(survey_id):
                await websocket.send_json({"event": "detection.verified", "survey_id": survey_id, "data": detection, "replay": True})
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        event_hub.unsubscribe(survey_id, queue)
