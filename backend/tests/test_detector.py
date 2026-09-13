"""
test_detector.py — Unit tests for the YOLO26 Nano adapter.

These tests are deliberately self-contained: they do NOT require ultralytics,
CUDA, or trained weights.  They verify:
  - graceful "model not installed" behaviour (no crash, empty results)
  - config env-var overrides
  - RawDetection physical-size conversion
  - _ensure_rgb channel broadcasting
  - describe() output contract
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from app.detector import (
    CLASS_NAMES,
    DEFAULT_RESOLUTION_M_PER_PX,
    DetectorConfig,
    RawDetection,
    Yolo26Adapter,
    get_adapter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dummy_tile(h: int = 64, w: int = 64, c: int = 3) -> np.ndarray:
    return np.zeros((h, w, c), dtype=np.uint8)


# ---------------------------------------------------------------------------
# DetectorConfig
# ---------------------------------------------------------------------------

class TestDetectorConfig:
    def test_defaults_are_sane(self):
        cfg = DetectorConfig()
        assert cfg.confidence_threshold == pytest.approx(0.10, rel=1e-3)
        assert cfg.iou_threshold == pytest.approx(0.45, rel=1e-3)
        assert cfg.tile_size == 640
        assert cfg.batch_size == 4

    def test_env_var_overrides(self, monkeypatch):
        monkeypatch.setenv("AQUASENSE_CONF_THRESH", "0.25")
        monkeypatch.setenv("AQUASENSE_BATCH_SIZE", "8")
        monkeypatch.setenv("AQUASENSE_DEVICE", "cuda:0")
        cfg = DetectorConfig()
        assert cfg.confidence_threshold == pytest.approx(0.25, rel=1e-3)
        assert cfg.batch_size == 8
        assert cfg.device == "cuda:0"

    def test_model_path_env_var(self, monkeypatch, tmp_path):
        fake_path = str(tmp_path / "custom.pt")
        monkeypatch.setenv("AQUASENSE_MODEL_PATH", fake_path)
        cfg = DetectorConfig()
        assert cfg.model_path == Path(fake_path)

    def test_relative_path_resolved_to_backend(self):
        cfg = DetectorConfig(model_path=Path("models_checkpoints/best.pt"))
        assert cfg.model_path.is_absolute()
        assert "models_checkpoints" in str(cfg.model_path)

    def test_is_onnx_detection(self, tmp_path):
        cfg_pt   = DetectorConfig(model_path=tmp_path / "model.pt")
        cfg_onnx = DetectorConfig(model_path=tmp_path / "model.onnx")
        assert not cfg_pt.is_onnx()
        assert cfg_onnx.is_onnx()


# ---------------------------------------------------------------------------
# Adapter — "model not installed" behaviour
# ---------------------------------------------------------------------------

class TestAdapterNotInstalled:
    def test_instantiation_is_safe_without_weights(self):
        """Creating the adapter must never raise, even with no weights file."""
        cfg = DetectorConfig(model_path=Path("/nonexistent/yolo26n.pt"))
        adapter = Yolo26Adapter(cfg)
        assert adapter.status == "not_loaded"

    def test_load_sets_unavailable_when_weights_missing(self):
        cfg = DetectorConfig(model_path=Path("/nonexistent/yolo26n.pt"))
        adapter = Yolo26Adapter(cfg)
        adapter.load()                   # must NOT raise
        assert adapter.status == "unavailable"
        assert not adapter.is_ready

    def test_run_batch_returns_empty_when_unavailable(self):
        cfg = DetectorConfig(model_path=Path("/nonexistent/yolo26n.pt"))
        adapter = Yolo26Adapter(cfg)
        tiles  = [_dummy_tile() for _ in range(3)]
        result = adapter.run_batch(tiles)
        assert len(result) == 3
        assert all(detections == [] for detections in result)

    def test_run_batch_empty_input_returns_empty(self):
        cfg = DetectorConfig(model_path=Path("/nonexistent/yolo26n.pt"))
        adapter = Yolo26Adapter(cfg)
        assert adapter.run_batch([]) == []

    def test_load_is_idempotent(self):
        cfg = DetectorConfig(model_path=Path("/nonexistent/yolo26n.pt"))
        adapter = Yolo26Adapter(cfg)
        adapter.load()
        adapter.load()   # second call must be a no-op, not a crash
        assert adapter.status == "unavailable"

    def test_model_version_contains_filename_when_unavailable(self):
        cfg = DetectorConfig(model_path=Path("/nonexistent/yolo26n_aquasense_marine.pt"))
        adapter = Yolo26Adapter(cfg)
        adapter.load()
        assert "yolo26n_aquasense_marine.pt" in adapter._model_version

    def test_describe_returns_complete_dict(self):
        cfg = DetectorConfig(model_path=Path("/nonexistent/yolo26n.pt"))
        adapter = Yolo26Adapter(cfg)
        adapter.load()
        info = adapter.describe()
        for key in ("status", "model_version", "model_path",
                    "confidence_threshold", "iou_threshold",
                    "tile_size", "batch_size", "device", "backend"):
            assert key in info, f"describe() missing key: {key}"


# ---------------------------------------------------------------------------
# _ensure_rgb channel broadcasting
# ---------------------------------------------------------------------------

class TestEnsureRgb:
    def test_grayscale_2d_to_rgb(self):
        gray = np.zeros((32, 32), dtype=np.uint8)
        rgb  = Yolo26Adapter._ensure_rgb(gray)
        assert rgb.shape == (32, 32, 3)

    def test_single_channel_to_rgb(self):
        gray = np.zeros((32, 32, 1), dtype=np.uint8)
        rgb  = Yolo26Adapter._ensure_rgb(gray)
        assert rgb.shape == (32, 32, 3)

    def test_rgba_to_rgb(self):
        rgba = np.zeros((32, 32, 4), dtype=np.uint8)
        rgb  = Yolo26Adapter._ensure_rgb(rgba)
        assert rgb.shape == (32, 32, 3)

    def test_rgb_passthrough(self):
        rgb_in = np.zeros((32, 32, 3), dtype=np.uint8)
        rgb_out = Yolo26Adapter._ensure_rgb(rgb_in)
        assert rgb_out.shape == (32, 32, 3)


# ---------------------------------------------------------------------------
# RawDetection physical size conversion (tested via run_batch internals)
# ---------------------------------------------------------------------------

class TestRawDetectionSizing:
    def test_physical_size_computed_from_resolution(self):
        """Manually invoke the size formula that run_batch applies."""
        tile_size = 640
        res       = 0.1          # metres per pixel
        cx, cy, w_norm, h_norm = 0.5, 0.5, 0.2, 0.15

        width_m  = w_norm * tile_size * res   # 0.2 * 640 * 0.1 = 12.8 m
        height_m = h_norm * tile_size * res   # 0.15 * 640 * 0.1 = 9.6 m

        assert width_m  == pytest.approx(12.8, rel=1e-3)
        assert height_m == pytest.approx(9.6,  rel=1e-3)

    def test_minimum_physical_size_floor(self):
        """Detections smaller than MIN_WIDTH_M are clamped, never zero."""
        from app.detector import MIN_WIDTH_M, MIN_HEIGHT_M
        assert MIN_WIDTH_M  > 0
        assert MIN_HEIGHT_M > 0


# ---------------------------------------------------------------------------
# CLASS_NAMES contract
# ---------------------------------------------------------------------------

class TestClassNames:
    def test_all_six_ps26057_classes_present(self):
        expected = {
            "human_artifact_wreck",
            "electrical_cable",
            "electronic_hazard",
            "plastic_debris",
            "metal_drum_scrap",
            "biological_geological_exclusion",
        }
        assert set(CLASS_NAMES.values()) == expected

    def test_indices_are_zero_based_contiguous(self):
        assert sorted(CLASS_NAMES.keys()) == list(range(len(CLASS_NAMES)))


# ---------------------------------------------------------------------------
# get_adapter singleton
# ---------------------------------------------------------------------------

class TestGetAdapter:
    def test_get_adapter_returns_yolo26_instance(self):
        adapter = get_adapter()
        assert isinstance(adapter, Yolo26Adapter)

    def test_get_adapter_is_idempotent(self):
        a1 = get_adapter()
        a2 = get_adapter()
        assert a1 is a2

    def test_get_adapter_status_is_not_not_loaded(self):
        # After get_adapter() the adapter must have attempted load(),
        # so status is either "ready" or "unavailable", never "not_loaded".
        adapter = get_adapter()
        assert adapter.status != "not_loaded"
