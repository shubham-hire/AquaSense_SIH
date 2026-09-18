"""Complete end-to-end integration tests for AquaSense."""
import io
from pathlib import Path

from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.repository import Repository
import app.main as main_module


@pytest.fixture()
def isolated_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """TestClient with fresh storage and one persistent ASGI event loop."""
    # The suite intentionally runs without model weights. Processing now
    # refuses to fabricate detections unless synthetic output is requested,
    # so these flow tests opt in explicitly.
    monkeypatch.setenv("AQUASENSE_ALLOW_SYNTHETIC_FALLBACK", "1")
    main_module.DATA_DIR = tmp_path
    main_module.UPLOAD_DIR = tmp_path / "uploads"
    main_module.ARTIFACT_DIR = tmp_path / "artifacts"
    main_module.MODELS_DIR = tmp_path / "models"
    for directory in (
        main_module.DATA_DIR,
        main_module.UPLOAD_DIR,
        main_module.ARTIFACT_DIR,
        main_module.MODELS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    main_module.repository = Repository(tmp_path / "e2e_test.sqlite3")
    # Entering the context keeps TestClient's portal/event loop alive across
    # requests while the application-owned processing task awaits to_thread().
    with TestClient(main_module.app) as client:
        yield client


def test_root_and_health_endpoints(isolated_client: TestClient):
    response = isolated_client.get("/")
    assert response.status_code == 200
    root_data = response.json()
    assert root_data["status"] == "online"
    assert "https://aqua-sense-sih.vercel.app" in root_data["cors_origins"]

    response = isolated_client.get("/health")
    assert response.status_code == 200
    health_data = response.json()
    assert health_data["status"] == "ok"
    assert health_data["storage"]["type"] == "sqlite"
    assert "model" in health_data


def test_full_pipeline_e2e(isolated_client: TestClient, tmp_path: Path):
    survey_id = "mission-e2e-001"
    image_buffer = io.BytesIO()
    Image.new("L", (64, 64), color=120).save(image_buffer, format="PNG")

    ingest_response = isolated_client.post(
        f"/v1/surveys/{survey_id}/ingest",
        files={"file": ("sonar_scan.png", image_buffer.getvalue(), "image/png")},
    )
    assert ingest_response.status_code == 200
    ingest_data = ingest_response.json()
    assert ingest_data["survey_id"] == survey_id
    assert ingest_data["qc_report"]["status"] in ("PASS", "WARNING")

    navigation_response = isolated_client.get(f"/v1/surveys/{survey_id}/navigation")
    assert navigation_response.status_code == 404

    with isolated_client.websocket_connect(f"/v1/surveys/{survey_id}/stream") as websocket:
        process_response = isolated_client.post(f"/v1/surveys/{survey_id}/process")
        assert process_response.status_code == 202
        assert process_response.json()["status"] == "processing_started"

        events_received = []
        while True:
            message = websocket.receive_json()
            events_received.append(message.get("event"))
            if message.get("event") in ("processing.complete", "processing.failed"):
                break
        assert "processing.started" in events_received
        assert "processing.complete" in events_received

    detection_response = isolated_client.get(f"/v1/surveys/{survey_id}/detections")
    assert detection_response.status_code == 200
    detections = detection_response.json()
    assert len(detections) >= 1

    first_detection = detections[0]
    detection_id = first_detection["id"]
    assert first_detection["survey_id"] == survey_id
    assert first_detection["position"]["position_source"] == "UNAVAILABLE"
    # No model weights are installed here, so results must be marked synthetic.
    assert first_detection["provenance"]["synthetic"] is True

    review_payload = {
        "outcome": "CONFIRMED",
        "note": "E2E automated validation test",
        "nav_trustworthy": True,
        "reviewed_by": "lead_operator",
    }
    review_response = isolated_client.put(
        f"/v1/detections/{detection_id}/review", json=review_payload
    )
    assert review_response.status_code == 200
    assert review_response.json()["ok"] is True

    get_review_response = isolated_client.get(f"/v1/detections/{detection_id}/review")
    assert get_review_response.status_code == 200
    review_data = get_review_response.json()
    assert review_data["outcome"] == "CONFIRMED"
    assert review_data["note"] == "E2E automated validation test"
    assert review_data["reviewed_by"] == "lead_operator"

    json_response = isolated_client.get(f"/v1/surveys/{survey_id}/report.json")
    assert json_response.status_code == 200
    json_data = json_response.json()
    assert json_data["report_metadata"]["survey_id"] == survey_id
    assert json_data["report_metadata"]["confirmed_count"] >= 1
    matched = [item for item in json_data["detections"] if item["id"] == detection_id]
    assert matched[0]["review"]["outcome"] == "CONFIRMED"

    csv_response = isolated_client.get(f"/v1/surveys/{survey_id}/report.csv")
    assert csv_response.status_code == 200
    assert "review_outcome" in csv_response.text
    assert "CONFIRMED" in csv_response.text

    geojson_response = isolated_client.get(f"/v1/surveys/{survey_id}/geojson")
    assert geojson_response.status_code == 200
    assert geojson_response.json()["type"] == "FeatureCollection"

    pdf_response = isolated_client.get(f"/v1/surveys/{survey_id}/report.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF")


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
                {
                    "ping_index": 4,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "latitude": 12.34,
                    "longitude": 76.78,
                    "valid_fix": True,
                    "altitude_m": 5.0,
                    "depth_m": 20.0,
                    "heading_deg": 90.0,
                    "speed_mps": 1.2,
                },
                {
                    "ping_index": 5,
                    "timestamp": None,
                    "latitude": None,
                    "longitude": None,
                    "valid_fix": False,
                },
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
