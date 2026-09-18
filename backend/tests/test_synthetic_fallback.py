"""The pipeline must never present fabricated detections as model output.

When the detector is unavailable the heuristic fallback produces randomised
boxes with plausible-looking confidences. Those are indistinguishable from
real contacts in the console, so processing refuses to run unless an operator
explicitly opts in, and any output it does produce is labelled synthetic.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.main as main_module
import app.pipeline as pipeline
from app.repository import Repository


class _UnavailableAdapter:
    """Stands in for a detector whose weights could not be loaded."""

    is_ready = False
    status = "unavailable"


@pytest.fixture()
def sonar_image(tmp_path: Path) -> Path:
    source = tmp_path / "scan.png"
    Image.fromarray(np.full((32, 32), 96, dtype=np.uint8)).save(source)
    return source


@pytest.fixture()
def unavailable_detector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "get_adapter", lambda: _UnavailableAdapter())


QC = {"resolution_meters_per_pixel": 0.1, "motion_artifact_rows": []}


def test_unavailable_model_refuses_instead_of_fabricating(
    sonar_image: Path, unavailable_detector: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(pipeline.SYNTHETIC_FALLBACK_ENV, raising=False)

    with pytest.raises(RuntimeError) as failure:
        pipeline.run_pipeline("survey-refused", sonar_image, QC, False)

    message = str(failure.value)
    assert "refused" in message
    assert pipeline.SYNTHETIC_FALLBACK_ENV in message


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_fallback_stays_disabled_for_non_affirmative_values(
    sonar_image: Path, unavailable_detector: None, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(pipeline.SYNTHETIC_FALLBACK_ENV, value)
    assert pipeline.synthetic_fallback_enabled() is False
    with pytest.raises(RuntimeError):
        pipeline.run_pipeline("survey-refused", sonar_image, QC, False)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_fallback_enabled_only_by_affirmative_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(pipeline.SYNTHETIC_FALLBACK_ENV, value)
    assert pipeline.synthetic_fallback_enabled() is True


def test_opted_in_fallback_labels_every_detection_as_synthetic(
    sonar_image: Path, unavailable_detector: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(pipeline.SYNTHETIC_FALLBACK_ENV, "1")

    detections = pipeline.run_pipeline("survey-demo", sonar_image, QC, False)

    assert detections
    for detection in detections:
        provenance = detection["provenance"]
        assert provenance["synthetic"] is True
        assert provenance["detector_backend"] == "heuristic-fallback"
        assert provenance["measurement_status"] == "SIMULATED"
        assert "SYNTHETIC DEMO DATA" in provenance["synthetic_warning"]
        assert "SYNTHETIC" in detection["model_version"]
        # A fabricated contact must not borrow a real class name.
        assert detection["classification"] not in set(pipeline.BEST_PT_CLASS_NAMES.values())


def test_real_model_output_is_marked_not_synthetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.detector import RawDetection

    class _Config:
        tile_size = 32
        batch_size = 1
        model_path = Path("/missing/test-best.pt")

    class _ReadyAdapter:
        is_ready = True
        config = _Config()

        def run_batch(self, tiles, resolution_m_per_px=None):
            return [
                [
                    RawDetection(
                        tile_index=0,
                        class_id=0,
                        classification="shipwreck",
                        raw_logit=0.9,
                        confidence_percent=90,
                        box_xywh_norm=(0.5, 0.5, 0.2, 0.2),
                        x_norm=0.4,
                        y_norm=0.4,
                        width_m=0.64,
                        height_m=0.64,
                        model_version="best.pt-test",
                    )
                ]
                for _tile in tiles
            ]

    source = tmp_path / "real.png"
    Image.fromarray(np.zeros((32, 32), dtype=np.uint8)).save(source)
    monkeypatch.setattr(pipeline, "get_adapter", lambda: _ReadyAdapter())

    detections = pipeline.run_pipeline("survey-real", source, QC, False)

    assert detections
    assert detections[0]["provenance"]["synthetic"] is False
    assert detections[0]["classification"] == "shipwreck"


def test_processing_reports_failure_and_stores_nothing_when_model_missing(
    tmp_path: Path, unavailable_detector: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(pipeline.SYNTHETIC_FALLBACK_ENV, raising=False)
    monkeypatch.setattr(main_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_module, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(main_module, "ARTIFACT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(main_module, "MODELS_DIR", tmp_path / "models")
    for directory in (
        main_module.UPLOAD_DIR,
        main_module.ARTIFACT_DIR,
        main_module.MODELS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main_module, "repository", Repository(tmp_path / "refusal.sqlite3"))

    survey_id = "survey-missing-model"
    buffer = io.BytesIO()
    Image.new("L", (32, 32), color=110).save(buffer, format="PNG")

    with TestClient(main_module.app) as client:
        ingest = client.post(
            f"/v1/surveys/{survey_id}/ingest",
            files={"file": ("scan.png", buffer.getvalue(), "image/png")},
        )
        assert ingest.status_code == 200

        with client.websocket_connect(f"/v1/surveys/{survey_id}/stream") as websocket:
            assert client.post(f"/v1/surveys/{survey_id}/process").status_code == 202
            while True:
                message = websocket.receive_json()
                if message.get("event") in ("processing.complete", "processing.failed"):
                    break

        assert message["event"] == "processing.failed"
        assert pipeline.SYNTHETIC_FALLBACK_ENV in message["detail"]

        detections = client.get(f"/v1/surveys/{survey_id}/detections")
        assert detections.status_code == 200
        assert detections.json() == []
