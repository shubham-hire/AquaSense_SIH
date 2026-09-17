from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from app.detector import RawDetection
from app.xtf import _ping_cross_track_resolution
import app.pipeline as pipeline


def test_xtf_resolution_uses_slant_range_per_sample():
    ping = SimpleNamespace(
        ping_chan_headers=[
            SimpleNamespace(SlantRange=100.0, NumSamples=1000),
            SimpleNamespace(SlantRange=120.0, NumSamples=1200),
        ],
        data=[np.zeros(1000), np.zeros(1200)],
    )
    assert _ping_cross_track_resolution(ping) == pytest.approx(0.1)


def test_xtf_resolution_refuses_missing_range():
    ping = SimpleNamespace(
        ping_chan_headers=[SimpleNamespace(SlantRange=0, NumSamples=1000)],
        data=[np.zeros(1000)],
    )
    assert _ping_cross_track_resolution(ping) is None


class _Config:
    tile_size = 64
    batch_size = 1
    model_path = Path("/missing/test-best.pt")


class _ResolutionAwareAdapter:
    is_ready = True
    config = _Config()

    def __init__(self):
        self.received_resolution = None

    def run_batch(self, tiles, resolution_m_per_px=None):
        self.received_resolution = resolution_m_per_px
        width = 0.1 * self.config.tile_size * resolution_m_per_px
        height = 0.2 * self.config.tile_size * resolution_m_per_px
        return [[RawDetection(
            tile_index=0,
            class_id=2,
            classification="cylinder",
            raw_logit=0.8,
            confidence_percent=80,
            box_xywh_norm=(0.5, 0.5, 0.1, 0.2),
            x_norm=0.45,
            y_norm=0.4,
            width_m=width,
            height_m=height,
            model_version="test-model",
        )]]


def test_pipeline_uses_source_resolution_for_dimensions(tmp_path, monkeypatch):
    source = tmp_path / "waterfall.png"
    Image.fromarray(np.zeros((64, 64), dtype=np.uint8)).save(source)
    adapter = _ResolutionAwareAdapter()
    monkeypatch.setattr(pipeline, "get_adapter", lambda: adapter)
    extraction = {
        "waterfall_path": str(source),
        "cross_track_resolution_m_per_pixel": 0.25,
        "measurement_source": "xtf_channel_slant_range",
        "navigation": [],
    }
    detections = pipeline.run_pipeline(
        "survey-resolution",
        source,
        {"resolution_meters_per_pixel": 0.1, "motion_artifact_rows": []},
        False,
        extraction,
    )
    assert adapter.received_resolution == pytest.approx(0.25)
    assert detections[0]["bounding_box"]["width_m"] == pytest.approx(1.6)
    assert detections[0]["bounding_box"]["height_m"] == pytest.approx(3.2)
    assert detections[0]["calibrated"] is False
    assert detections[0]["provenance"]["measurement_status"] == "SOURCE_DERIVED"
    assert detections[0]["provenance"]["measurement_source"] == "xtf_channel_slant_range"


def test_pipeline_marks_default_resolution_uncalibrated(tmp_path, monkeypatch):
    source = tmp_path / "image.png"
    Image.fromarray(np.zeros((64, 64), dtype=np.uint8)).save(source)
    adapter = _ResolutionAwareAdapter()
    monkeypatch.setattr(pipeline, "get_adapter", lambda: adapter)
    detections = pipeline.run_pipeline(
        "survey-default",
        source,
        {"resolution_meters_per_pixel": 0.1, "motion_artifact_rows": []},
        False,
    )
    assert detections[0]["provenance"]["measurement_status"] == "UNCALIBRATED"
    assert detections[0]["provenance"]["measurement_source"] == "uncalibrated_default"
