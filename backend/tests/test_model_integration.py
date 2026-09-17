from pathlib import Path

import numpy as np
from PIL import Image

import app.pipeline as pipeline
from app.detector import RawDetection


class _Config:
    tile_size = 32
    batch_size = 2
    model_path = Path("/missing/test-best.pt")


class _FakeAdapter:
    is_ready = True
    config = _Config()

    def run_batch(self, tiles, resolution_m_per_px=None):
        return [
            [
                RawDetection(
                    tile_index=index,
                    class_id=3,
                    classification="legacy-name-that-must-not-leak",
                    raw_logit=0.91,
                    confidence_percent=91,
                    box_xywh_norm=(0.5, 0.5, 0.25, 0.25),
                    x_norm=0.375,
                    y_norm=0.375,
                    width_m=0.8,
                    height_m=0.8,
                    model_version="best.pt-test",
                )
            ]
            for index, _tile in enumerate(tiles)
        ]


def test_ready_model_is_used_and_class_mapping_matches_checkpoint(tmp_path, monkeypatch):
    source = tmp_path / "sonar.png"
    Image.fromarray(np.full((32, 32), 127, dtype=np.uint8)).save(source)
    monkeypatch.setattr(pipeline, "get_adapter", lambda: _FakeAdapter())

    detections = pipeline.run_pipeline(
        "survey-model",
        source,
        {
            "resolution_meters_per_pixel": 0.1,
            "motion_artifact_rows": [],
        },
        False,
    )

    assert len(detections) == 1
    detection = detections[0]
    assert detection["classification"] == "ghost_net"
    assert detection["confidence_percent"] == 91
    assert detection["model_version"] == "best.pt-test"
    assert detection["provenance"]["detector_backend"] == "ultralytics-yolo26"
    assert detection["position"]["position_source"] == "UNAVAILABLE"


def test_ready_model_with_no_objects_does_not_use_heuristic(tmp_path, monkeypatch):
    source = tmp_path / "empty-scene.png"
    Image.fromarray(np.zeros((32, 32), dtype=np.uint8)).save(source)
    adapter = _FakeAdapter()
    adapter.run_batch = lambda tiles, resolution_m_per_px=None: [[] for _ in tiles]
    monkeypatch.setattr(pipeline, "get_adapter", lambda: adapter)

    detections = pipeline.run_pipeline(
        "survey-empty",
        source,
        {
            "resolution_meters_per_pixel": 0.1,
            "motion_artifact_rows": [],
        },
        False,
    )

    assert detections == []
