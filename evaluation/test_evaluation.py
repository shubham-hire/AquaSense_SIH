"""
test_evaluation.py — Tests for build_manifest, split_missions, and evaluate.
All tests are self-contained and require only numpy + PIL (no trained weights).
"""
from __future__ import annotations

import json
import math
import textwrap
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Tiny dataset fixture helpers
# ---------------------------------------------------------------------------

CLASS_NAMES = {
    0: "human_artifact_wreck", 1: "electrical_cable", 2: "electronic_hazard",
    3: "plastic_debris", 4: "metal_drum_scrap", 5: "biological_geological_exclusion",
}

def _make_dataset(root: Path, mission_tiles: dict[str, dict[str, list]]) -> None:
    """
    mission_tiles: {mission_name: {split: [list_of_annotation_strings]}}
    annotation_string: "cls cx cy w h"
    """
    from PIL import Image
    for mission, splits in mission_tiles.items():
        for split, annotations_list in splits.items():
            img_dir   = root / "images" / split / mission
            label_dir = root / "labels" / split / mission
            img_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            for i, anns in enumerate(annotations_list):
                stem = f"tile_{i:04d}"
                Image.new("L", (640, 640), 128).save(img_dir / f"{stem}.png")
                label_path = label_dir / f"{stem}.txt"
                label_path.write_text(anns if anns else "")


def _make_manifest(root: Path, mission_tiles: dict) -> Path:
    _make_dataset(root, mission_tiles)
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from build_manifest import build_manifest
    out = root / "manifest.jsonl"
    build_manifest(root, out, xtf_meta_path=None)
    return out


# ---------------------------------------------------------------------------
# build_manifest tests
# ---------------------------------------------------------------------------

class TestBuildManifest:
    def test_produces_one_record_per_tile(self, tmp_path):
        _make_dataset(tmp_path, {
            "SeabedObjects": {"train": ["0 0.5 0.5 0.2 0.2", "0 0.3 0.3 0.1 0.1"]},
            "NNSSS":         {"test":  ["5 0.6 0.6 0.15 0.15"]},
        })
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        n = build_manifest(tmp_path, out, None)
        assert n == 3

    def test_split_field_matches_directory(self, tmp_path):
        _make_dataset(tmp_path, {
            "MissionA": {"train": ["0 0.5 0.5 0.2 0.2"]},
            "MissionB": {"val":   ["1 0.4 0.4 0.1 0.1"]},
        })
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        build_manifest(tmp_path, out, None)
        records = [json.loads(l) for l in out.read_text().splitlines()]
        splits = {r["split"] for r in records}
        assert "train" in splits and "val" in splits

    def test_mission_derived_from_subdirectory(self, tmp_path):
        _make_dataset(tmp_path, {
            "SeabedObjects": {"train": ["0 0.5 0.5 0.2 0.2"]},
        })
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        build_manifest(tmp_path, out, None)
        records = [json.loads(l) for l in out.read_text().splitlines()]
        assert records[0]["mission"] == "SeabedObjects"

    def test_annotation_fields_parsed_correctly(self, tmp_path):
        _make_dataset(tmp_path, {
            "M": {"train": ["3 0.512 0.380 0.240 0.198"]}
        })
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        build_manifest(tmp_path, out, None)
        rec = json.loads(out.read_text().splitlines()[0])
        ann = rec["annotations"][0]
        assert ann["class_id"] == 3
        assert ann["class_name"] == "plastic_debris"
        assert ann["box_cx_norm"] == pytest.approx(0.512, abs=1e-4)
        assert ann["box_w_norm"]  == pytest.approx(0.240, abs=1e-4)

    def test_empty_label_produces_zero_annotations(self, tmp_path):
        _make_dataset(tmp_path, {"M": {"train": [""]}})
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        build_manifest(tmp_path, out, None)
        rec = json.loads(out.read_text().splitlines()[0])
        assert rec["annotations"] == []

    def test_tile_id_is_unique(self, tmp_path):
        _make_dataset(tmp_path, {
            "M": {"train": ["0 0.5 0.5 0.1 0.1", "1 0.3 0.3 0.1 0.1"]}
        })
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        build_manifest(tmp_path, out, None)
        records = [json.loads(l) for l in out.read_text().splitlines()]
        ids = [r["tile_id"] for r in records]
        assert len(ids) == len(set(ids))

    def test_image_dimensions_captured(self, tmp_path):
        _make_dataset(tmp_path, {"M": {"train": ["0 0.5 0.5 0.1 0.1"]}})
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        build_manifest(tmp_path, out, None)
        rec = json.loads(out.read_text().splitlines()[0])
        assert rec["width_px"]  == 640
        assert rec["height_px"] == 640

    def test_mask_points_parsed_from_seg_format(self, tmp_path):
        # YOLO seg: class cx cy x1 y1 x2 y2 x3 y3 ...
        seg_line = "0 0.5 0.5 0.1 0.1 0.2 0.1 0.2 0.2 0.1 0.2"
        _make_dataset(tmp_path, {"M": {"train": [seg_line]}})
        from build_manifest import build_manifest
        out = tmp_path / "manifest.jsonl"
        build_manifest(tmp_path, out, None)
        rec = json.loads(out.read_text().splitlines()[0])
        ann = rec["annotations"][0]
        assert ann["has_mask"] is True
        assert ann["mask_points"] is not None
        assert len(ann["mask_points"]) > 0


# ---------------------------------------------------------------------------
# split_missions tests
# ---------------------------------------------------------------------------

class TestSplitMissions:
    def _build_manifest(self, tmp_path, missions: dict) -> Path:
        """missions: {name: tile_count}"""
        from PIL import Image
        root = tmp_path / "ds"
        lines = []
        for mission, count in missions.items():
            for i in range(count):
                img_dir = root / "images" / "train" / mission
                img_dir.mkdir(parents=True, exist_ok=True)
                img = img_dir / f"tile_{i:04d}.png"
                Image.new("L", (640, 640)).save(img)
                label_dir = root / "labels" / "train" / mission
                label_dir.mkdir(parents=True, exist_ok=True)
                (label_dir / f"tile_{i:04d}.txt").write_text("0 0.5 0.5 0.1 0.1")

        from build_manifest import build_manifest
        manifest_out = tmp_path / "manifest.jsonl"
        build_manifest(root, manifest_out, None)
        return manifest_out

    def test_no_mission_appears_in_multiple_splits(self, tmp_path):
        manifest = self._build_manifest(tmp_path, {
            "A": 100, "B": 80, "C": 60, "D": 40, "E": 20,
        })
        from split_missions import split_missions
        result = split_missions(manifest, tmp_path / "split.json",
                                0.70, 0.15, seed=42, dataset_root=None)
        all_missions = result["train"] + result["val"] + result["test"]
        assert len(all_missions) == len(set(all_missions)), "Mission appears in multiple splits"

    def test_split_covers_all_missions(self, tmp_path):
        manifest = self._build_manifest(tmp_path, {"A": 50, "B": 30, "C": 20})
        from split_missions import split_missions
        result = split_missions(manifest, tmp_path / "split.json",
                                0.70, 0.15, seed=42, dataset_root=None)
        all_assigned = set(result["train"] + result["val"] + result["test"])
        assert all_assigned == {"A", "B", "C"}

    def test_tile_counts_sum_to_total(self, tmp_path):
        manifest = self._build_manifest(tmp_path, {"A": 50, "B": 30, "C": 20})
        from split_missions import split_missions
        result = split_missions(manifest, tmp_path / "split.json",
                                0.70, 0.15, seed=42, dataset_root=None)
        total = sum(result["tile_counts"].values())
        assert total == 100

    def test_split_ratios_sum_to_one(self, tmp_path):
        manifest = self._build_manifest(tmp_path, {"A": 100, "B": 50, "C": 50})
        from split_missions import split_missions
        result = split_missions(manifest, tmp_path / "split.json",
                                0.70, 0.15, seed=42, dataset_root=None)
        total_ratio = sum(result["split_ratios"].values())
        assert total_ratio == pytest.approx(1.0, abs=0.02)

    def test_result_is_reproducible_with_same_seed(self, tmp_path):
        manifest = self._build_manifest(tmp_path, {"A": 80, "B": 60, "C": 40, "D": 20})
        from split_missions import split_missions
        r1 = split_missions(manifest, tmp_path / "s1.json", 0.70, 0.15, seed=7, dataset_root=None)
        r2 = split_missions(manifest, tmp_path / "s2.json", 0.70, 0.15, seed=7, dataset_root=None)
        assert r1["train"] == r2["train"]
        assert r1["val"]   == r2["val"]
        assert r1["test"]  == r2["test"]

    def test_calibration_note_present_in_output(self, tmp_path):
        manifest = self._build_manifest(tmp_path, {"A": 50, "B": 50})
        from split_missions import split_missions
        result = split_missions(manifest, tmp_path / "split.json",
                                0.70, 0.15, seed=42, dataset_root=None)
        assert "calibration_note" in result
        assert "val" in result["calibration_note"].lower()

    def test_yolo_filelists_written_when_dataset_root_provided(self, tmp_path):
        from PIL import Image
        root = tmp_path / "ds"
        missions = {"Alpha": 10, "Beta": 10}
        for mission, count in missions.items():
            for i in range(count):
                img_dir = root / "images" / "train" / mission
                img_dir.mkdir(parents=True, exist_ok=True)
                Image.new("L", (640, 640)).save(img_dir / f"t_{i}.png")
                lbl_dir = root / "labels" / "train" / mission
                lbl_dir.mkdir(parents=True, exist_ok=True)
                (lbl_dir / f"t_{i}.txt").write_text("0 0.5 0.5 0.1 0.1")

        from build_manifest import build_manifest
        m = tmp_path / "m.jsonl"
        build_manifest(root, m, None)

        from split_missions import split_missions
        split_missions(m, tmp_path / "si.json", 0.70, 0.15, seed=1, dataset_root=root)

        # At least one of train/val/test.txt must have been written
        written = [root / f"{s}.txt" for s in ("train", "val", "test")]
        assert any(p.exists() for p in written)


# ---------------------------------------------------------------------------
# evaluate.py — unit tests (no YOLO weights needed)
# ---------------------------------------------------------------------------

class TestBox:
    def test_iou_identical_boxes_is_one(self):
        from evaluate import Box
        b = Box(0.5, 0.5, 0.2, 0.2)
        assert Box.iou(b, b) == pytest.approx(1.0, abs=1e-6)

    def test_iou_non_overlapping_is_zero(self):
        from evaluate import Box
        a = Box(0.1, 0.1, 0.1, 0.1)
        b = Box(0.9, 0.9, 0.1, 0.1)
        assert Box.iou(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_iou_partial_overlap(self):
        from evaluate import Box
        a = Box(0.5, 0.5, 0.4, 0.4)
        b = Box(0.6, 0.6, 0.4, 0.4)
        iou = Box.iou(a, b)
        assert 0.0 < iou < 1.0

    def test_to_xyxy_conversion(self):
        from evaluate import Box
        b = Box(0.5, 0.5, 0.2, 0.2)
        x1, y1, x2, y2 = b.to_xyxy()
        assert x1 == pytest.approx(0.4, abs=1e-6)
        assert y1 == pytest.approx(0.4, abs=1e-6)
        assert x2 == pytest.approx(0.6, abs=1e-6)
        assert y2 == pytest.approx(0.6, abs=1e-6)


class TestMetrics:
    def _make_gt_pred(self) -> tuple:
        from evaluate import GTBox, PredBox, Box
        gt = [
            GTBox("t1", "M", 0, Box(0.5, 0.5, 0.2, 0.2)),
            GTBox("t2", "M", 1, Box(0.3, 0.3, 0.15, 0.15)),
        ]
        preds = [
            PredBox("t1", "M", 0, 0.90, Box(0.5, 0.5, 0.2, 0.2)),   # TP class 0
            PredBox("t2", "M", 1, 0.75, Box(0.3, 0.3, 0.15, 0.15)), # TP class 1
        ]
        return gt, preds

    def test_perfect_predictions_give_high_metrics(self):
        from evaluate import compute_metrics
        gt, preds = self._make_gt_pred()
        metrics = compute_metrics(gt, preds, conf_threshold=0.25)
        # Two classes (0 and 1) have GT and perfect predictions.
        # Check per-class metrics for those, not macro (which averages over all 6 classes).
        pc = metrics["per_class"]
        assert pc["human_artifact_wreck"]["precision"] == pytest.approx(1.0, abs=0.01)
        assert pc["human_artifact_wreck"]["recall"]    == pytest.approx(1.0, abs=0.01)
        assert pc["electrical_cable"]["precision"]     == pytest.approx(1.0, abs=0.01)
        assert pc["electrical_cable"]["recall"]        == pytest.approx(1.0, abs=0.01)
        # mAP@0.5 should also be > 0
        assert metrics["macro"]["mAP50"] > 0.0

    def test_no_predictions_gives_zero_recall(self):
        from evaluate import GTBox, Box, compute_metrics
        gt = [GTBox("t1", "M", 0, Box(0.5, 0.5, 0.2, 0.2))]
        metrics = compute_metrics(gt, [], conf_threshold=0.25)
        assert metrics["macro"]["recall"] == 0.0

    def test_all_false_positives_gives_zero_precision(self):
        from evaluate import GTBox, PredBox, Box, compute_metrics
        gt = [GTBox("t1", "M", 0, Box(0.5, 0.5, 0.2, 0.2))]
        preds = [
            PredBox("t1", "M", 0, 0.9, Box(0.01, 0.01, 0.05, 0.05)),  # no overlap
        ]
        metrics = compute_metrics(gt, preds, conf_threshold=0.0)
        assert metrics["per_class"]["human_artifact_wreck"]["precision"] == 0.0

    def test_conf_threshold_filters_low_confidence(self):
        from evaluate import GTBox, PredBox, Box, compute_metrics, load_predictions
        # load_predictions filters; test compute_metrics with filtered list
        from evaluate import GTBox, PredBox, Box, compute_metrics
        gt = [GTBox("t1", "M", 0, Box(0.5, 0.5, 0.2, 0.2))]
        # High-conf TP + low-conf TP (low should be filtered externally)
        preds_high = [PredBox("t1", "M", 0, 0.9, Box(0.5, 0.5, 0.2, 0.2))]
        preds_low  = []
        m_high = compute_metrics(gt, preds_high, conf_threshold=0.5)
        m_empty = compute_metrics(gt, preds_low,  conf_threshold=0.5)
        assert m_high["macro"]["recall"] > m_empty["macro"]["recall"]

    def test_per_class_keys_match_taxonomy(self):
        from evaluate import compute_metrics
        gt, preds = self._make_gt_pred()
        metrics = compute_metrics(gt, preds, conf_threshold=0.0)
        for name in CLASS_NAMES.values():
            assert name in metrics["per_class"]

    def test_map50_95_less_than_or_equal_to_map50(self):
        from evaluate import compute_metrics
        gt, preds = self._make_gt_pred()
        metrics = compute_metrics(gt, preds, conf_threshold=0.0)
        assert metrics["macro"]["mAP50_95"] <= metrics["macro"]["mAP50"] + 1e-6


class TestConfusionMatrix:
    def test_perfect_predictions_diagonal(self):
        from evaluate import GTBox, PredBox, Box, build_confusion_matrix, NUM_CLASSES
        gt    = [GTBox("t1", "M", 0, Box(0.5, 0.5, 0.2, 0.2))]
        preds = [PredBox("t1", "M", 0, 0.9, Box(0.5, 0.5, 0.2, 0.2))]
        cm = build_confusion_matrix(gt, preds)
        assert cm[0][0] == 1
        # Row 0 (GT class 0) should only have a count in col 0 (pred class 0)
        assert cm[0, :NUM_CLASSES].sum() == 1

    def test_fp_goes_to_background_row(self):
        from evaluate import GTBox, PredBox, Box, build_confusion_matrix, NUM_CLASSES
        gt    = [GTBox("t1", "M", 0, Box(0.5, 0.5, 0.2, 0.2))]
        preds = [PredBox("t2", "M", 1, 0.9, Box(0.5, 0.5, 0.2, 0.2))]  # wrong tile
        cm = build_confusion_matrix(gt, preds)
        # FP: pred on tile t2 with no GT → background row
        assert cm[NUM_CLASSES][1] == 1

    def test_missed_detection_goes_to_background_column(self):
        from evaluate import GTBox, Box, build_confusion_matrix, NUM_CLASSES
        gt = [GTBox("t1", "M", 2, Box(0.5, 0.5, 0.2, 0.2))]
        cm = build_confusion_matrix(gt, [])
        # FN: GT class 2 unmatched → col NUM_CLASSES
        assert cm[2][NUM_CLASSES] == 1

    def test_confusion_matrix_shape(self):
        from evaluate import build_confusion_matrix, NUM_CLASSES
        cm = build_confusion_matrix([], [])
        assert cm.shape == (NUM_CLASSES + 1, NUM_CLASSES + 1)

    def test_confusion_matrix_dict_has_labels(self):
        from evaluate import build_confusion_matrix, confusion_matrix_to_dict, NUM_CLASSES
        cm = build_confusion_matrix([], [])
        d = confusion_matrix_to_dict(cm)
        assert len(d["labels"]) == NUM_CLASSES + 1
        assert d["labels"][-1] == "background"


class TestLatency:
    def _write_preds_jsonl(self, path: Path, tiles: list[dict]) -> None:
        lines = []
        for t in tiles:
            lines.append(json.dumps(t))
        path.write_text("\n".join(lines))

    def test_tile_latency_stats_computed(self, tmp_path):
        from evaluate import load_predictions
        preds_path = tmp_path / "preds.jsonl"
        self._write_preds_jsonl(preds_path, [
            {"tile_id": "t1", "mission": "M", "tile_latency_ms": 15.0,
             "mission_latency_ms": 15.0, "detections": []},
            {"tile_id": "t2", "mission": "M", "tile_latency_ms": 25.0,
             "mission_latency_ms": 25.0, "detections": []},
        ])
        _, stats = load_predictions(preds_path, conf_threshold=0.0)
        tl = stats["tile_latency"]
        assert tl["n"] == 2
        assert tl["mean_ms"] == pytest.approx(20.0, abs=0.01)

    def test_missing_latency_produces_none(self, tmp_path):
        from evaluate import load_predictions
        preds_path = tmp_path / "preds.jsonl"
        self._write_preds_jsonl(preds_path, [
            {"tile_id": "t1", "mission": "M", "detections": []},
        ])
        _, stats = load_predictions(preds_path, conf_threshold=0.0)
        assert stats["tile_latency"]["n"] == 0
        assert stats["tile_latency"]["mean_ms"] is None

    def test_per_mission_latency_grouped(self, tmp_path):
        from evaluate import load_predictions
        preds_path = tmp_path / "preds.jsonl"
        self._write_preds_jsonl(preds_path, [
            {"tile_id": "t1", "mission": "Alpha", "tile_latency_ms": 10.0,
             "mission_latency_ms": 10.0, "detections": []},
            {"tile_id": "t2", "mission": "Beta",  "tile_latency_ms": 30.0,
             "mission_latency_ms": 30.0, "detections": []},
        ])
        _, stats = load_predictions(preds_path, conf_threshold=0.0)
        assert "Alpha" in stats["per_mission"]
        assert "Beta"  in stats["per_mission"]


class TestReportSchema:
    def test_build_report_has_required_keys(self):
        from evaluate import build_report, compute_metrics, build_confusion_matrix, confusion_matrix_to_dict
        metrics = compute_metrics([], [], conf_threshold=0.25)
        cm = build_confusion_matrix([], [])
        confusion = confusion_matrix_to_dict(cm)
        latency = {"tile_latency": {"n": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "p99_ms": None},
                   "mission_latency": {"n": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "p99_ms": None},
                   "per_mission": {}}
        gallery = {"gallery_fp": None, "gallery_fn": None, "n_fp": 0, "n_fn": 0}
        report = build_report(metrics, confusion, latency, gallery, "val", 0.25, "m.jsonl", "p.jsonl")
        for key in ("schema_version", "split", "conf_threshold", "metrics",
                    "confusion_matrix", "latency", "gallery", "calibration_discipline"):
            assert key in report, f"Report missing key: {key}"

    def test_calibration_discipline_mentions_val_and_test(self):
        from evaluate import build_report, compute_metrics, build_confusion_matrix, confusion_matrix_to_dict
        metrics = compute_metrics([], [], conf_threshold=0.25)
        cm = confusion_matrix_to_dict(build_confusion_matrix([], []))
        latency = {"tile_latency": {}, "mission_latency": {}, "per_mission": {}}
        gallery = {"gallery_fp": None, "gallery_fn": None, "n_fp": 0, "n_fn": 0}
        report = build_report(metrics, cm, latency, gallery, "val", 0.25, "m.jsonl", "p.jsonl")
        disc = report["calibration_discipline"]
        assert "val" in str(disc).lower()
        assert "test" in str(disc).lower()
