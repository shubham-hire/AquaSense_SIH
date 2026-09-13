"""
test_e2e_flow.py — Complete End-to-End integration test for AquaSense.

Verifies the entire lifecycle:
  1. Health & Root endpoints (CORS, Persistent Storage diagnostics)
  2. Survey ingestion (POST /v1/surveys/{id}/ingest)
  3. Processing & Progressive WebSocket streaming (WS /v1/surveys/{id}/stream)
  4. Detection listing & Refusal invariant check (GET /v1/surveys/{id}/detections)
  5. Operator review workflow (PUT/GET /v1/detections/{id}/review)
  6. Export delivery (JSON, CSV, GeoJSON, PDF)
"""
import io
import time
from pathlib import Path
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.repository import Repository
import app.main as main_module


@pytest.fixture()
def isolated_client(tmp_path: Path):
    """TestClient with fresh isolated storage paths."""
    main_module.DATA_DIR = tmp_path
    main_module.UPLOAD_DIR = tmp_path / "uploads"
    main_module.ARTIFACT_DIR = tmp_path / "artifacts"
    main_module.MODELS_DIR = tmp_path / "models"
    for d in (main_module.DATA_DIR, main_module.UPLOAD_DIR, main_module.ARTIFACT_DIR, main_module.MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    main_module.repository = Repository(tmp_path / "e2e_test.sqlite3")
    client = TestClient(main_module.app)
    yield client


def test_root_and_health_endpoints(isolated_client: TestClient):
    # 1. Root info
    resp = isolated_client.get("/")
    assert resp.status_code == 200
    root_data = resp.json()
    assert root_data["status"] == "online"
    assert "https://aqua-sense-sih.vercel.app" in root_data["cors_origins"]

    # 2. Health check
    resp = isolated_client.get("/health")
    assert resp.status_code == 200
    health_data = resp.json()
    assert health_data["status"] == "ok"
    assert "storage" in health_data
    assert health_data["storage"]["type"] == "sqlite"
    assert "model" in health_data


def test_full_pipeline_e2e(isolated_client: TestClient, tmp_path: Path):
    survey_id = "mission-e2e-001"

    # Create dummy survey image
    img_buf = io.BytesIO()
    Image.new("L", (64, 64), color=120).save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    # 1. Ingest survey
    ingest_resp = isolated_client.post(
        f"/v1/surveys/{survey_id}/ingest",
        files={"file": ("sonar_scan.png", img_bytes, "image/png")},
    )
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["survey_id"] == survey_id
    assert ingest_data["qc_report"]["status"] in ("PASS", "WARNING")

    # Raster uploads contain no source navigation and must not receive a mock map.
    navigation_resp = isolated_client.get(f"/v1/surveys/{survey_id}/navigation")
    assert navigation_resp.status_code == 404

    # 2. Connect to WebSocket stream and trigger processing
    with isolated_client.websocket_connect(f"/v1/surveys/{survey_id}/stream") as ws:
        # Trigger processing
        proc_resp = isolated_client.post(f"/v1/surveys/{survey_id}/process")
        assert proc_resp.status_code == 202
        assert proc_resp.json()["status"] == "processing_started"

        # Receive stream events
        events_received = []
        while True:
            msg = ws.receive_json()
            events_received.append(msg.get("event"))
            if msg.get("event") in ("processing.complete", "processing.failed"):
                break

        assert "processing.started" in events_received
        assert "processing.complete" in events_received

    # 3. Fetch detections
    det_resp = isolated_client.get(f"/v1/surveys/{survey_id}/detections")
    assert det_resp.status_code == 200
    detections = det_resp.json()
    assert len(detections) >= 1

    first_det = detections[0]
    det_id = first_det["id"]
    assert first_det["survey_id"] == survey_id
    # Ensure unlocated refusal invariant holds for synthetic PNG
    assert first_det["position"]["position_source"] == "UNAVAILABLE"

    # 4. Operator Review workflow
    review_payload = {
        "outcome": "CONFIRMED",
        "note": "E2E automated validation test",
        "nav_trustworthy": True,
        "reviewed_by": "lead_operator",
    }
    review_resp = isolated_client.put(f"/v1/detections/{det_id}/review", json=review_payload)
    assert review_resp.status_code == 200
    assert review_resp.json()["ok"] is True

    get_review_resp = isolated_client.get(f"/v1/detections/{det_id}/review")
    assert get_review_resp.status_code == 200
    review_data = get_review_resp.json()
    assert review_data["outcome"] == "CONFIRMED"
    assert review_data["note"] == "E2E automated validation test"
    assert review_data["reviewed_by"] == "lead_operator"

    # 5. Export validation
    # JSON Report
    json_resp = isolated_client.get(f"/v1/surveys/{survey_id}/report.json")
    assert json_resp.status_code == 200
    json_data = json_resp.json()
    assert json_data["report_metadata"]["survey_id"] == survey_id
    assert json_data["report_metadata"]["confirmed_count"] >= 1
    matched = [d for d in json_data["detections"] if d["id"] == det_id]
    assert matched[0]["review"]["outcome"] == "CONFIRMED"

    # CSV Report
    csv_resp = isolated_client.get(f"/v1/surveys/{survey_id}/report.csv")
    assert csv_resp.status_code == 200
    assert "review_outcome" in csv_resp.text
    assert "CONFIRMED" in csv_resp.text

    # GeoJSON
    geojson_resp = isolated_client.get(f"/v1/surveys/{survey_id}/geojson")
    assert geojson_resp.status_code == 200
    assert geojson_resp.json()["type"] == "FeatureCollection"

    # PDF Report
    pdf_resp = isolated_client.get(f"/v1/surveys/{survey_id}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")


def test_navigation_endpoint_exposes_only_valid_extracted_fixes(isolated_client: TestClient):
    survey_id = "mission-nav-001"
    main_module.repository.save_ingest(
        survey_id,
        "/tmp/source.xtf",
        {"status": "PASS"},
        {
            "format": "XTF",
            "ping_count": 3,
            "valid_navigation_pings": 1,
            "navigation": [
                {"ping_index": 4, "timestamp": "2026-01-01T00:00:00Z", "latitude": 12.34, "longitude": 76.78, "valid_fix": True, "altitude_m": 5.0, "depth_m": 20.0, "heading_deg": 90.0, "speed_mps": 1.2},
                {"ping_index": 5, "timestamp": None, "latitude": None, "longitude": None, "valid_fix": False},
            ],
        },
    )
    response = isolated_client.get(f"/v1/surveys/{survey_id}/navigation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "XTF"
    assert payload["total_ping_count"] == 3
    assert payload["valid_navigation_pings"] == 1
    assert payload["map_center"] == [12.34, 76.78]
    assert len(payload["track_points"]) == 1
    assert payload["track_points"][0]["ping_index"] == 4
