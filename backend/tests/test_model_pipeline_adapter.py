"""Model-ready pipeline tests without requiring trained YOLO weights."""
from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from app.detector import RawDetection
from app.pipeline import inspect_file, run_pipeline


class StubReadyAdapter:
    """A deterministic YOLO26 stand-in used to exercise the production bridge."""

    is_ready = True
    config = SimpleNamespace(tile_size=16)

    def __init__(self) -> None:
        self.calls: list[tuple[int, float]] = []

    def describe(self) -> dict:
        return {"backend": "ultralytics", "model_version": "yolo26n-test (best.pt)"}

    def run_batch(self, tiles, resolution_m_per_px: float):
        self.calls.append((len(tiles), resolution_m_per_px))
        first = RawDetection(
            tile_index=0,
            class_id=4,
            classification="metal_drum_scrap",
            raw_logit=0.82,
            confidence_percent=82,
            box_xywh_norm=(0.5, 0.5, 0.25, 0.25),
            x_norm=0.375,
            y_norm=0.375,
            width_m=0.4,
            height_m=0.4,
            model_version="yolo26n-test (best.pt)",
        )
        return [[first], *([[] for _ in tiles[1:]])]


def test_ready_adapter_drives_pipeline_and_refuses_image_coordinates(tmp_path, monkeypatch):
    source = tmp_path / "survey.png"
    Image.new("L", (24, 24), color=120).save(source)
    qc, extraction = inspect_file("survey-model", source, source.name)
    adapter = StubReadyAdapter()
    monkeypatch.setattr("app.pipeline.get_adapter", lambda: adapter)

    result = run_pipeline("survey-model", source, qc.model_dump(), dsp_applied=False, extraction=extraction)

    assert adapter.calls == [(4, 0.1)]
    assert len(result) == 1
    detection = result[0]
    assert detection["classification"] == "metal_drum_scrap"
    assert detection["model_version"] == "yolo26n-test (best.pt)"
    assert detection["provenance"]["detector_backend"] == "ultralytics"
    assert detection["position"] == {
        "latitude": None,
        "longitude": None,
        "position_source": "UNAVAILABLE",
        "refusal_reason": "Valid navigation metadata was not available for this detection ping.",
    }
    assert len(detection["verification_features"]) == 10


def test_ready_adapter_uses_only_the_backprojected_valid_navigation_fix(tmp_path, monkeypatch):
    source = tmp_path / "waterfall.png"
    Image.new("L", (16, 16), color=150).save(source)
    qc, _ = inspect_file("survey-nav", source, source.name)
    extraction = {
        "waterfall_path": str(source),
        "navigation": [
            {
                "row_index": row,
                "ping_index": row,
                "timestamp": f"2026-01-01T00:00:{row:02d}+00:00",
                "valid_fix": row == 8,
                "latitude": 12.34 if row == 8 else None,
                "longitude": 76.78 if row == 8 else None,
            }
            for row in range(16)
        ],
    }
    monkeypatch.setattr("app.pipeline.get_adapter", StubReadyAdapter)

    result = run_pipeline("survey-nav", source, qc.model_dump(), dsp_applied=False, extraction=extraction)

    assert len(result) == 1
    assert result[0]["ping_index"] == 8
    assert result[0]["position"] == {
        "latitude": 12.34,
        "longitude": 76.78,
        "position_source": "GPS_FIX",
        "refusal_reason": None,
    }
