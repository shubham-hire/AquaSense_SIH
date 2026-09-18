from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .pipeline import SUPPORTED_FORMATS, inspect_file, iter_pipeline
from .repository import Repository
from .schemas import Detection, ReviewDecision
from .streaming import event_hub

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("AQUASENSE_DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
ARTIFACT_DIR = DATA_DIR / "artifacts"
MODELS_DIR = Path(os.getenv("AQUASENSE_MODELS_DIR", DATA_DIR / "models"))
for directory in (DATA_DIR, UPLOAD_DIR, ARTIFACT_DIR, MODELS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
repository = Repository(DATA_DIR / "aquasense.sqlite3")
app = FastAPI(title="AquaSense API", version="0.1.0", description="Offline-first sonar survey processing API")

# Survey identifiers are used to build upload filenames, artifact directories,
# export filenames, and storage keys. Only an explicit allowlist is accepted so
# untrusted input can never contribute path separators or traversal segments.
SURVEY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
SURVEY_ID_RULE = (
    "survey_id must start with a letter or digit and may contain up to 128 "
    "letters, digits, dots, underscores, or hyphens"
)


def validate_survey_id(survey_id: str) -> str:
    """Reject any survey identifier that could escape the storage directories."""
    if not SURVEY_ID_PATTERN.fullmatch(survey_id) or ".." in survey_id:
        raise HTTPException(422, SURVEY_ID_RULE)
    return survey_id


def _contained_path(directory: Path, name: str) -> Path:
    """Resolve `name` inside `directory`, refusing anything that escapes it."""
    base = directory.resolve()
    candidate = (base / name).resolve()
    if candidate != base and base not in candidate.parents:
        raise HTTPException(422, SURVEY_ID_RULE)
    return candidate


DEFAULT_ORIGINS = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "https://aqua-sense-sih.vercel.app",
]
env_origins = [origin.strip() for origin in os.getenv("AQUASENSE_CORS_ORIGINS", "").split(",") if origin.strip()]
cors_origins = list(dict.fromkeys(DEFAULT_ORIGINS + env_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {"name": "AquaSense API", "status": "online", "version": "0.1.0", "docs_url": "/docs", "health_url": "/health", "cors_origins": cors_origins}


def get_detection(detection_id: str) -> dict:
    detection = repository.detection(detection_id)
    if not detection:
        raise HTTPException(404, "Detection not found")
    return detection


def survey_detections(survey_id: str) -> list[dict]:
    validate_survey_id(survey_id)
    if not repository.ingest_info(survey_id):
        raise HTTPException(404, "Survey has not been ingested")
    return repository.detections_for_survey(survey_id)


@app.get("/health")
def health() -> dict:
    import shutil
    try:
        stat = shutil.disk_usage(DATA_DIR)
        disk_total_gb = round(stat.total / (1024 ** 3), 2)
        disk_free_gb = round(stat.free / (1024 ** 3), 2)
    except Exception:
        disk_total_gb = disk_free_gb = None
    model_path = Path(os.getenv("AQUASENSE_MODEL_PATH", MODELS_DIR / "yolo26n_aquasense_marine.pt"))
    return {
        "status": "ok", "service": "aquasense-api", "version": "0.1.0",
        "storage": {"type": "sqlite", "data_dir": str(DATA_DIR), "disk_total_gb": disk_total_gb, "disk_free_gb": disk_free_gb},
        "cors_origins": cors_origins,
        "model": {"configured_path": str(model_path), "weights_present": model_path.exists()},
    }


@app.post("/v1/surveys/{survey_id}/ingest")
async def ingest_survey(survey_id: str, file: UploadFile = File(...)) -> dict:
    validate_survey_id(survey_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(415, f"Supported formats: {', '.join(SUPPORTED_FORMATS)}")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = _contained_path(UPLOAD_DIR, f"{survey_id}-{uuid4()}{suffix}")
    size = 0
    with destination.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > 500 * 1024 * 1024:
                destination.unlink(missing_ok=True)
                raise HTTPException(413, "Upload exceeds the 500 MB offline processing limit")
            output.write(chunk)
    artifact_dir = _contained_path(ARTIFACT_DIR, f"{survey_id}-{uuid4()}")
    try:
        qc, extraction = inspect_file(survey_id, destination, file.filename or destination.name, artifact_dir)
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    repository.save_ingest(survey_id, str(destination), qc.model_dump(mode="json"), extraction)
    return {
        "survey_id": survey_id,
        "qc_report": qc,
        "xtf_extraction": {"ping_count": extraction["ping_count"], "valid_navigation_pings": extraction["valid_navigation_pings"], "waterfall_shape": extraction["waterfall_shape"]} if extraction else None,
    }


def _collect_pipeline_results(survey_id: str, source_path: str, qc: dict, dsp_applied: bool, extraction: dict | None) -> list[dict]:
    """Run CPU/GPU-bound inference outside the asyncio event-loop thread."""
    return list(iter_pipeline(survey_id, Path(source_path), qc, dsp_applied, extraction))


async def _process_in_background(survey_id: str, source_path: str, qc: dict, extraction: dict | None, dsp_applied: bool) -> None:
    try:
        await event_hub.publish(survey_id, "processing.started")
        await event_hub.publish(survey_id, "processing.stage", stage="detection", progress_percent=25)
        detections = await asyncio.to_thread(
            _collect_pipeline_results,
            survey_id,
            source_path,
            qc,
            dsp_applied,
            extraction,
        )
        for number, detection in enumerate(detections, start=1):
            await event_hub.publish(survey_id, "processing.stage", stage="verification", progress_percent=75)
            await event_hub.publish(survey_id, "detection.verified", data=detection, sequence=number)
            await asyncio.sleep(0)
        repository.replace_detections(survey_id, detections)
        await event_hub.publish(survey_id, "processing.complete", detection_count=len(detections), progress_percent=100)
    except Exception as exc:
        await event_hub.publish(survey_id, "processing.failed", detail=str(exc))


@app.post("/v1/surveys/{survey_id}/process", status_code=202)
async def process_survey(survey_id: str, dsp_applied: bool = False) -> dict:
    validate_survey_id(survey_id)
    info = repository.ingest_info(survey_id)
    if not info:
        raise HTTPException(409, "Ingest a survey before processing it")
    source_path, qc, extraction = info
    asyncio.create_task(_process_in_background(survey_id, source_path, qc, extraction, dsp_applied))
    return {"survey_id": survey_id, "status": "processing_started", "stream_url": f"/v1/surveys/{survey_id}/stream"}


@app.get("/v1/surveys/{survey_id}/processing")
def processing_status(survey_id: str) -> dict:
    validate_survey_id(survey_id)
    return event_hub._state.get(survey_id, {"event": "stream.ready", "survey_id": survey_id})


@app.get("/v1/surveys/{survey_id}/detections", response_model=list[Detection])
def list_detections(survey_id: str) -> list[dict]:
    return survey_detections(survey_id)


@app.get("/v1/surveys/{survey_id}/sonar")
def sonar_metadata(survey_id: str) -> dict:
    validate_survey_id(survey_id)
    info = repository.ingest_info(survey_id)
    if not info or not info[2]:
        raise HTTPException(404, "No extracted sonar payload is available for this survey")
    return {key: value for key, value in info[2].items() if key not in {"waterfall_path", "metadata_path"}}


@app.get("/v1/surveys/{survey_id}/navigation")
def survey_navigation(survey_id: str) -> dict:
    validate_survey_id(survey_id)
    info = repository.ingest_info(survey_id)
    if not info or not info[2]:
        raise HTTPException(404, "No extracted navigation is available for this survey")
    extraction = info[2]
    track_points = [
        {
            "ping_index": item["ping_index"], "timestamp": item.get("timestamp"),
            "latitude": item["latitude"], "longitude": item["longitude"],
            "altitude_m": item.get("altitude_m"), "depth_m": item.get("depth_m"),
            "heading_deg": item.get("heading_deg"), "speed_mps": item.get("speed_mps"),
        }
        for item in extraction.get("navigation", [])
        if item.get("valid_fix") and item.get("latitude") is not None and item.get("longitude") is not None
    ]
    map_center = [
        sum(point["latitude"] for point in track_points) / len(track_points),
        sum(point["longitude"] for point in track_points) / len(track_points),
    ] if track_points else None
    return {
        "survey_id": survey_id, "format": extraction.get("format"),
        "total_ping_count": extraction.get("ping_count", 0),
        "valid_navigation_pings": extraction.get("valid_navigation_pings", 0),
        "map_center": map_center, "track_points": track_points,
    }


@app.get("/v1/surveys/{survey_id}/waterfall.png")
def waterfall_image(survey_id: str) -> Response:
    validate_survey_id(survey_id)
    info = repository.ingest_info(survey_id)
    if not info or not info[2] or not Path(info[2]["waterfall_path"]).is_file():
        raise HTTPException(404, "No extracted XTF waterfall image is available for this survey")
    return Response(Path(info[2]["waterfall_path"]).read_bytes(), media_type="image/png")


@app.get("/v1/detections/{detection_id}", response_model=Detection)
def detection_detail(detection_id: str) -> dict:
    item = get_detection(detection_id)
    review = repository.get_review(detection_id)
    return {**item, "review": review} if review is not None else item


@app.get("/v1/detections/{detection_id}/explain")
def explain_detection(detection_id: str) -> dict:
    item = get_detection(detection_id)
    return {"detection_id": item["id"], "verification_features": item["verification_features"], "feature_weights": item["feature_weights"], "calibrated": item["calibrated"], "model_version": item["model_version"]}


@app.put("/v1/detections/{detection_id}/review", status_code=200)
def submit_review(detection_id: str, decision: ReviewDecision) -> dict:
    if not repository.detection(detection_id):
        raise HTTPException(404, "Detection not found")
    repository.save_review(detection_id, decision.model_dump(mode="json"))
    return {"ok": True, "detection_id": detection_id, "outcome": decision.outcome}


@app.get("/v1/detections/{detection_id}/review")
def get_review(detection_id: str) -> dict:
    get_detection(detection_id)
    review = repository.get_review(detection_id)
    if review is None:
        raise HTTPException(404, "No review has been submitted for this detection")
    return review


@app.delete("/v1/detections/{detection_id}/review", status_code=200)
def delete_review(detection_id: str) -> dict:
    get_detection(detection_id)
    if not repository.delete_review(detection_id):
        raise HTTPException(404, "No review has been submitted for this detection")
    return {"ok": True, "detection_id": detection_id}


@app.get("/v1/surveys/{survey_id}/report.json")
def json_report(survey_id: str) -> Response:
    items = survey_detections(survey_id)
    reviews = repository.reviews_for_survey(survey_id)
    enriched = [{**d, "review": reviews.get(d["id"])} for d in items]
    payload = {
        "report_metadata": {
            "survey_id": survey_id, "total_detections": len(enriched),
            "unlocated_refusal_count": sum(d["position"]["position_source"] == "UNAVAILABLE" for d in enriched),
            "reviewed_count": sum(d["review"] is not None for d in enriched),
            "confirmed_count": sum((d["review"] or {}).get("outcome") == "CONFIRMED" for d in enriched),
            "rejected_fp_count": sum((d["review"] or {}).get("outcome") == "REJECTED_FP" for d in enriched),
            "corrected_count": sum((d["review"] or {}).get("outcome") == "CORRECTED" for d in enriched),
        },
        "detections": enriched,
    }
    return Response(json.dumps(payload, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{survey_id}-report.json"'})


@app.get("/v1/surveys/{survey_id}/report.csv")
def csv_report(survey_id: str) -> Response:
    items = survey_detections(survey_id)
    reviews = repository.reviews_for_survey(survey_id)
    output = io.StringIO()
    fieldnames = [
        "detection_id", "latitude", "longitude", "classification", "confidence_percent",
        "width_m", "height_m", "position_source", "low_data_quality", "calibrated",
        "survey_id", "ping_timestamp", "review_outcome", "corrected_class",
        "nav_trustworthy", "operator_note", "reviewed_at", "reviewed_by",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for d in items:
        rv = reviews.get(d["id"]) or {}
        writer.writerow({
            "detection_id": d["id"], "latitude": d["position"]["latitude"],
            "longitude": d["position"]["longitude"], "classification": d["classification"],
            "confidence_percent": d["confidence_percent"], "width_m": d["bounding_box"]["width_m"],
            "height_m": d["bounding_box"]["height_m"], "position_source": d["position"]["position_source"],
            "low_data_quality": d["low_data_quality"], "calibrated": d["calibrated"],
            "survey_id": survey_id, "ping_timestamp": d["ping_timestamp"],
            "review_outcome": rv.get("outcome", ""), "corrected_class": rv.get("corrected_class", ""),
            "nav_trustworthy": rv.get("nav_trustworthy", ""), "operator_note": rv.get("note", ""),
            "reviewed_at": rv.get("reviewed_at", ""), "reviewed_by": rv.get("reviewed_by", ""),
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{survey_id}-report.csv"'})


@app.get("/v1/surveys/{survey_id}/geojson")
def geojson_report(survey_id: str) -> dict:
    items = survey_detections(survey_id)
    reviews = repository.reviews_for_survey(survey_id)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [d["position"]["longitude"], d["position"]["latitude"]]},
            "properties": {
                "id": d["id"], "classification": d["classification"],
                "confidence_percent": d["confidence_percent"], "width_m": d["bounding_box"]["width_m"],
                "height_m": d["bounding_box"]["height_m"],
                "review_outcome": (reviews.get(d["id"]) or {}).get("outcome"),
                "corrected_class": (reviews.get(d["id"]) or {}).get("corrected_class"),
                "nav_trustworthy": (reviews.get(d["id"]) or {}).get("nav_trustworthy"),
            },
        }
        for d in items if d["position"]["position_source"] == "GPS_FIX"
    ]
    return {"type": "FeatureCollection", "name": f"AquaSense_{survey_id}_hazards", "features": features}


@app.get("/v1/surveys/{survey_id}/report.pdf")
def pdf_report(survey_id: str) -> Response:
    items = survey_detections(survey_id)
    pdf = io.BytesIO()
    page = canvas.Canvas(pdf, pagesize=letter)
    page.setTitle(f"AquaSense mission report — {survey_id}")
    page.drawString(72, 750, f"AquaSense mission report: {survey_id}")
    page.drawString(72, 730, f"Detections: {len(items)} | Unlocated: {sum(d['position']['position_source'] == 'UNAVAILABLE' for d in items)}")
    y = 700
    for d in items:
        page.drawString(72, y, f"{d['id'][:8]}  {d['classification']}  {d['confidence_percent']}%  {d['position']['position_source']}")
        y -= 20
        if y < 70:
            page.showPage()
            y = 750
    page.save()
    return Response(pdf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{survey_id}-report.pdf"'})


@app.websocket("/v1/surveys/{survey_id}/stream")
async def stream_detections(websocket: WebSocket, survey_id: str) -> None:
    if not SURVEY_ID_PATTERN.fullmatch(survey_id) or ".." in survey_id:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = event_hub.subscribe(survey_id)
    try:
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
