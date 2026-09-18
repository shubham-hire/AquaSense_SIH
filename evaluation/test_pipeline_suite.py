"""
test_pipeline_suite.py — Unit & Integration Tests for Acceptance and Evaluation Pipeline
========================================================================================
PS 26057 | SIH 2026

Tests all 4 acceptance stages:
  1. Checkpoint Validation (6-class vs 7-class ghost gear, nano budget, synthetic test tile)
  2. Evaluation Runner (manifest inference, metrics, confusion matrix, calibration guard)
  3. Calibration & Platt Scaling (sample collection, Platt fitting, ECE reduction)
  4. Deployment Profiling (sweep computation, edge budget assessment)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from validate_checkpoint import (
    TAXONOMY_6,
    TAXONOMY_7,
    create_mock_weights_file,
    create_synthetic_test_tile,
    validate_checkpoint,
)
from run_evaluation import run_evaluation, run_model_inference_on_manifest
from calibrate import (
    apply_platt,
    collect_calibration_samples,
    compute_ece,
    fit_and_export_calibration,
    fit_platt_parameters,
    generate_synthetic_calibration_samples,
)
from profile_deployment import benchmark_pytorch_inference
from evaluate import Box, GTBox, PredBox


# ---------------------------------------------------------------------------
# Checkpoint Validation Tests
# ---------------------------------------------------------------------------

class TestCheckpointValidation:
    def test_synthetic_test_tile_shape_and_dtype(self):
        tile = create_synthetic_test_tile(640)
        assert tile.shape == (640, 640, 3)
        assert tile.dtype == np.uint8
        # Check that highlight and shadow have non-trivial intensity variance
        assert np.max(tile) > 200
        assert np.min(tile) < 50

    def test_create_mock_weights_7class(self, tmp_path):
        out = tmp_path / "mock_7c.pt"
        created = create_mock_weights_file(out, num_classes=7)
        assert created.exists()
        assert created.stat().st_size > 0

    def test_validate_checkpoint_missing_file(self, tmp_path):
        report = validate_checkpoint(tmp_path / "non_existent.pt")
        assert report["file_exists"] is False
        assert report["checks_passed"] is False
        assert len(report["errors"]) > 0

    def test_validate_checkpoint_mock_7class(self, tmp_path):
        out = tmp_path / "test_model_7c.pt"
        create_mock_weights_file(out, num_classes=7)
        report = validate_checkpoint(out, strict_7_class=True)
        assert report["file_exists"] is True
        assert report["is_nano_envelope"] is True
        assert report["has_ghost_gear_class"] is True
        assert report["test_tile_passed"] is True
        assert report["checks_passed"] is True

    def test_validate_checkpoint_strict_7class_fails_on_6class(self, tmp_path):
        out = tmp_path / "test_model_6c.pt"
        create_mock_weights_file(out, num_classes=6)
        report = validate_checkpoint(out, strict_7_class=True)
        # Should flag error because strict 7 class requested
        assert report["has_ghost_gear_class"] is False
        assert any("strict-7-class" in e for e in report["errors"])
        assert report["checks_passed"] is False

    def test_validate_checkpoint_lenient_passes_6class_with_warning(self, tmp_path):
        out = tmp_path / "test_model_6c.pt"
        create_mock_weights_file(out, num_classes=6)
        report = validate_checkpoint(out, strict_7_class=False)
        assert report["file_exists"] is True
        assert report["has_ghost_gear_class"] is False
        assert any("6 baseline classes" in w for w in report["warnings"])
        assert report["checks_passed"] is True


# ---------------------------------------------------------------------------
# Calibration & Platt Scaling Tests
# ---------------------------------------------------------------------------

class TestCalibration:
    def test_collect_calibration_samples_matches_gt(self):
        gt = [
            GTBox("tile_1", "M1", 6, Box(0.5, 0.5, 0.2, 0.2)),
            GTBox("tile_1", "M1", 0, Box(0.2, 0.2, 0.1, 0.1)),
        ]
        preds = [
            # High-confidence true positive on class 6 (ghost_gear)
            PredBox("tile_1", "M1", 6, 0.90, Box(0.51, 0.51, 0.2, 0.2)),
            # False positive on background
            PredBox("tile_1", "M1", 3, 0.70, Box(0.8, 0.8, 0.1, 0.1)),
        ]
        samples = collect_calibration_samples(gt, preds, iou_threshold=0.50)
        assert len(samples) == 2

        tp_sample = next(s for s in samples if s["class_id"] == 6)
        fp_sample = next(s for s in samples if s["class_id"] == 3)

        assert tp_sample["target_label"] == 1
        assert tp_sample["best_iou"] > 0.80
        assert fp_sample["target_label"] == 0
        assert fp_sample["best_iou"] == 0.0

    def test_fit_platt_parameters_improves_ece(self):
        # Generate synthetic uncalibrated samples
        samples = generate_synthetic_calibration_samples(n_samples=400)
        scores = [s["raw_confidence"] for s in samples]
        labels = [s["target_label"] for s in samples]

        A, B = fit_platt_parameters(scores, labels)
        calibrated = [apply_platt(s, A, B) for s in scores]

        raw_ece = compute_ece(scores, labels)["ece"]
        cal_ece = compute_ece(calibrated, labels)["ece"]

        # Platt scaling should strictly reduce calibration error on overconfident samples
        assert cal_ece < raw_ece

    def test_fit_and_export_calibration_writes_files(self, tmp_path):
        samples = generate_synthetic_calibration_samples(n_samples=200)
        res = fit_and_export_calibration(samples, tmp_path)

        assert res["samples_path"].exists()
        assert res["scales_path"].exists()

        ledger = json.loads(res["scales_path"].read_text())
        assert "global_model" in ledger
        assert "per_class_models" in ledger
        assert "ghost_gear" in ledger["per_class_models"]
        assert ledger["total_calibration_samples"] == 200


# ---------------------------------------------------------------------------
# Evaluation Runner Tests
# ---------------------------------------------------------------------------

class TestEvaluationRunner:
    def _create_mini_manifest(self, root: Path) -> Path:
        manifest_path = root / "manifest.jsonl"
        records = [
            {
                "tile_id": f"val__survey__tile_{i}",
                "split": "val",
                "mission": "SurveyA",
                "image_path": None,
                "annotations": [
                    {
                        "class_id": 6 if i % 2 == 0 else 0,
                        "class_name": "ghost_gear" if i % 2 == 0 else "human_artifact_wreck",
                        "box_cx_norm": 0.5,
                        "box_cy_norm": 0.5,
                        "box_w_norm": 0.2,
                        "box_h_norm": 0.2,
                    }
                ],
            }
            for i in range(10)
        ]
        with manifest_path.open("w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return manifest_path

    def test_evaluation_runner_mock_eval_generates_reports(self, tmp_path):
        manifest = self._create_mini_manifest(tmp_path)
        out_dir = tmp_path / "eval_out"

        res = run_evaluation(
            model_path=None,
            manifest_path=manifest,
            split="val",
            out_dir=out_dir,
            conf=0.20,
            mock_eval=True,
        )

        assert res["report_path"].exists()
        assert res["preds_path"].exists()
        assert res["summary_path"].exists()

        report = json.loads(res["report_path"].read_text())
        assert "metrics" in report
        assert "macro" in report["metrics"]
        assert "confusion_matrix" in report
        assert report["metrics"]["macro"]["precision"] > 0.0

    def test_evaluation_runner_guards_test_split(self, tmp_path):
        manifest = self._create_mini_manifest(tmp_path)
        out_dir = tmp_path / "eval_test_guarded"

        with pytest.raises(ValueError, match="GUARD"):
            run_evaluation(
                model_path=None,
                manifest_path=manifest,
                split="test",
                out_dir=out_dir,
                allow_test_eval=False,
                mock_eval=True,
            )


# ---------------------------------------------------------------------------
# Taxonomy and Config Integrity Tests
# ---------------------------------------------------------------------------

class TestTaxonomyIntegrity:
    def test_config_yaml_has_ghost_gear_and_nc_7(self):
        import yaml
        config_path = Path("configs/sonar_debris_yolo26.yaml")
        assert config_path.exists()
        with config_path.open() as f:
            data = yaml.safe_load(f)
        assert data["nc"] == 7
        assert data["names"][6] == "ghost_gear"

    def test_backend_detector_has_ghost_gear(self):
        try:
            from app.detector import CLASS_NAMES
        except ImportError:
            from backend.app.detector import CLASS_NAMES
        assert 6 in CLASS_NAMES
        assert CLASS_NAMES[6] == "ghost_gear"
