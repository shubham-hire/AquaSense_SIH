"""Opt-in end-to-end test that executes the committed checkpoint through AquaSense."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.detector import DetectorConfig, Yolo26Adapter
from app.schemas import Detection
import app.pipeline as pipeline

EXPECTED_SHA256 = "342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53"
EXPECTED_CLASSES = {
    0: "shipwreck",
    1: "submarine_pipeline",
    2: "cylinder",
    3: "ghost_net",
    4: "ghost_pot_trap",
    5: "plastic_debris",
    6: "metal_debris",
}

pytestmark = pytest.mark.skipif(
    os.getenv("AQUASENSE_RUN_REAL_MODEL_TEST") != "1",
    reason="real checkpoint test is opt-in",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_committed_checkpoint_runs_through_real_pipeline(tmp_path, monkeypatch):
    model_path = Path(os.environ["AQUASENSE_MODEL_PATH"]).resolve()
    assert model_path.is_file(), f"checkpoint missing: {model_path}"
    assert _sha256(model_path) == EXPECTED_SHA256

    adapter = Yolo26Adapter(
        DetectorConfig(
            model_path=model_path,
            device="cpu",
            tile_size=640,
            batch_size=1,
            confidence_threshold=0.10,
        )
    )
    adapter.load()
    assert adapter.is_ready
    assert adapter._model.names == EXPECTED_CLASSES

    calls = 0
    original_run_batch = adapter.run_batch

    def counted_run_batch(tiles, resolution_m_per_px=None):
        nonlocal calls
        calls += 1
        return original_run_batch(tiles, resolution_m_per_px)

    adapter.run_batch = counted_run_batch
    monkeypatch.setattr(pipeline, "get_adapter", lambda: adapter)

    # A deterministic sonar-like grayscale pattern exercises image QC, tiling,
    # real model inference, pipeline mapping, refusal, and response validation.
    x = np.linspace(0, 255, 640, dtype=np.uint8)
    image = np.tile(x, (640, 1))
    image[240:400, 280:360] = 255 - image[240:400, 280:360]
    source = tmp_path / "synthetic-sonar.png"
    Image.fromarray(image, mode="L").save(source)

    qc, extraction = pipeline.inspect_file(
        "real-model-e2e", source, source.name
    )
    detections = pipeline.run_pipeline(
        "real-model-e2e",
        source,
        qc.model_dump(mode="json"),
        dsp_applied=False,
        extraction=extraction,
    )

    assert calls == 1, "pipeline did not execute the configured model adapter"
    assert isinstance(detections, list)
    for item in detections:
        validated = Detection.model_validate(item)
        assert validated.position.position_source == "UNAVAILABLE"
        assert item["classification"] in EXPECTED_CLASSES.values()
        assert item["provenance"]["detector_backend"] == "ultralytics-yolo26"
        assert item["provenance"]["model_sha256"] == EXPECTED_SHA256
        assert item["provenance"]["detector_backend"] != "heuristic-fallback"
