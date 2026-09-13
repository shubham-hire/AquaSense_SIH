#!/usr/bin/env python3
"""
evaluate.py — AquaSense YOLO26 Nano Model Evaluation Suite
===========================================================
PS 26057 | SIH 2026

Accepts predictions from the trained YOLO26 Nano model and produces:

  1. Precision, Recall, F1, mAP@0.5, mAP@0.5:0.95  (per-class + macro)
  2. Per-class confusion matrix
  3. False-positive / missed-detection gallery  (PNG grid, configurable limit)
  4. Tile-level and full-mission inference latency statistics
  5. JSON report compatible with the AquaSense backend / UI API

CALIBRATION DISCIPLINE
----------------------
  --split val   → use for Platt-scaling / confidence calibration only.
                  Results here guide threshold selection; never final numbers.
  --split test  → held-out benchmark. Do NOT call with --split test while
                  tuning thresholds or the test-set guarantee is void.
  The script prints a prominent warning if --split test is used and
  --allow-test-eval is not explicitly passed.

Input formats
-------------
Predictions JSONL (one prediction per tile):
  {
    "tile_id": "test__SeabedObjects__wreck_001",
    "mission": "SeabedObjects",
    "detections": [
      {
        "class_id": 0, "class_name": "human_artifact_wreck",
        "confidence": 0.81,
        "box_cx_norm": 0.512, "box_cy_norm": 0.380,
        "box_w_norm": 0.240, "box_h_norm": 0.198,
        "tile_latency_ms": 18.4
      }
    ],
    "mission_latency_ms": 18.4
  }

Ground-truth comes from the manifest produced by build_manifest.py.

Usage
-----
    # Calibration on val (safe to run freely)
    python evaluation/evaluate.py \\
        --manifest  evaluation/manifest.jsonl \\
        --preds     evaluation/predictions_val.jsonl \\
        --split     val \\
        --out-dir   evaluation/reports/val_run_01 \\
        --conf      0.25

    # Final held-out test (requires explicit flag)
    python evaluation/evaluate.py \\
        --manifest  evaluation/manifest.jsonl \\
        --preds     evaluation/predictions_test.jsonl \\
        --split     test --allow-test-eval \\
        --out-dir   evaluation/reports/test_final \\
        --conf      0.35
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

import numpy as np

# PIL is only needed for the gallery; graceful skip if unavailable
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    warnings.warn("Pillow not installed — gallery images will be skipped.")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLASS_NAMES: dict[int, str] = {
    0: "human_artifact_wreck",
    1: "electrical_cable",
    2: "electronic_hazard",
    3: "plastic_debris",
    4: "metal_drum_scrap",
    5: "biological_geological_exclusion",
}
NUM_CLASSES = len(CLASS_NAMES)
IOU_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]  # for mAP@0.5:0.95


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Box(NamedTuple):
    cx: float; cy: float; w: float; h: float

    def to_xyxy(self) -> tuple[float, float, float, float]:
        x1, y1 = self.cx - self.w / 2, self.cy - self.h / 2
        return x1, y1, x1 + self.w, y1 + self.h

    @staticmethod
    def iou(a: "Box", b: "Box") -> float:
        ax1, ay1, ax2, ay2 = a.to_xyxy()
        bx1, by1, bx2, by2 = b.to_xyxy()
        ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        if inter == 0:
            return 0.0
        union = (a.w * a.h) + (b.w * b.h) - inter
        return inter / max(union, 1e-9)


class GTBox(NamedTuple):
    tile_id: str; mission: str; class_id: int; box: Box


class PredBox(NamedTuple):
    tile_id: str; mission: str; class_id: int; confidence: float; box: Box


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_ground_truth(manifest_path: Path, split: str) -> list[GTBox]:
    gt: list[GTBox] = []
    with manifest_path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["split"] != split:
                continue
            for ann in rec.get("annotations", []):
                gt.append(GTBox(
                    tile_id=rec["tile_id"],
                    mission=rec["mission"],
                    class_id=ann["class_id"],
                    box=Box(ann["box_cx_norm"], ann["box_cy_norm"],
                            ann["box_w_norm"], ann["box_h_norm"]),
                ))
    return gt


def load_predictions(preds_path: Path, conf_threshold: float) -> tuple[list[PredBox], dict]:
    """Returns (pred_boxes, latency_stats)."""
    preds: list[PredBox] = []
    tile_latencies: list[float] = []
    mission_latencies: dict[str, list[float]] = defaultdict(list)

    with preds_path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line.strip())
            tile_id = rec["tile_id"]
            mission = rec.get("mission", "unknown")
            tile_lat = rec.get("tile_latency_ms")
            mission_lat = rec.get("mission_latency_ms")

            if tile_lat is not None:
                tile_latencies.append(float(tile_lat))
            if mission_lat is not None:
                mission_latencies[mission].append(float(mission_lat))

            for det in rec.get("detections", []):
                conf = float(det["confidence"])
                if conf < conf_threshold:
                    continue
                preds.append(PredBox(
                    tile_id=tile_id,
                    mission=mission,
                    class_id=int(det["class_id"]),
                    confidence=conf,
                    box=Box(det["box_cx_norm"], det["box_cy_norm"],
                            det["box_w_norm"], det["box_h_norm"]),
                ))

    latency_stats = _latency_stats(tile_latencies, mission_latencies)
    return preds, latency_stats


def _latency_stats(tile_latencies: list[float], mission_latencies: dict[str, list[float]]) -> dict:
    def _summarise(values: list[float]) -> dict:
        if not values:
            return {"n": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "p99_ms": None}
        arr = sorted(values)
        n = len(arr)
        return {
            "n": n,
            "mean_ms": round(sum(arr) / n, 3),
            "p50_ms":  round(arr[int(n * 0.50)], 3),
            "p95_ms":  round(arr[min(int(n * 0.95), n - 1)], 3),
            "p99_ms":  round(arr[min(int(n * 0.99), n - 1)], 3),
        }

    per_mission = {}
    all_mission_total: list[float] = []
    for mission, lats in mission_latencies.items():
        per_mission[mission] = _summarise(lats)
        all_mission_total.extend(lats)

    return {
        "tile_latency":    _summarise(tile_latencies),
        "mission_latency": _summarise(all_mission_total),
        "per_mission":     per_mission,
    }


# ---------------------------------------------------------------------------
# Matching & AP computation
# ---------------------------------------------------------------------------

def _match_predictions(
    gt: list[GTBox],
    preds: list[PredBox],
    iou_threshold: float,
) -> tuple[dict[int, list[tuple[float, int]]], dict[int, int]]:
    """
    For each class, match predictions to GT boxes at a given IoU threshold.

    Returns:
        class_matches: {class_id: [(confidence, tp_flag), ...]}  sorted by -conf
        class_n_gt:    {class_id: total GT count}
    """
    # Index GT by (tile_id, class_id)
    gt_index: dict[tuple[str, int], list[tuple[GTBox, bool]]] = defaultdict(list)
    for g in gt:
        gt_index[(g.tile_id, g.class_id)].append((g, False))  # (gt_box, matched)

    class_matches: dict[int, list[tuple[float, int]]] = defaultdict(list)
    class_n_gt: dict[int, int] = defaultdict(int)

    for g in gt:
        class_n_gt[g.class_id] += 1

    # Sort predictions by descending confidence
    sorted_preds = sorted(preds, key=lambda p: -p.confidence)

    # Track which GT boxes are already consumed per (tile_id, class_id)
    matched_gt: dict[tuple[str, int], list[bool]] = {
        key: [False] * len(items)
        for key, items in gt_index.items()
    }

    for pred in sorted_preds:
        key = (pred.tile_id, pred.class_id)
        gt_list = gt_index.get(key, [])
        matched_flags = matched_gt.get(key, [])

        best_iou = 0.0
        best_idx = -1
        for idx, (g, _) in enumerate(gt_list):
            if matched_flags[idx]:
                continue
            iou = Box.iou(pred.box, g.box)
            if iou > best_iou:
                best_iou = iou
                best_idx = idx

        if best_iou >= iou_threshold and best_idx >= 0:
            matched_flags[best_idx] = True
            class_matches[pred.class_id].append((pred.confidence, 1))   # TP
        else:
            class_matches[pred.class_id].append((pred.confidence, 0))   # FP

    return class_matches, class_n_gt


def _average_precision(confidences: list[float], tp_flags: list[int], n_gt: int) -> float:
    """Compute AP using the 101-point interpolation (COCO-style)."""
    if n_gt == 0:
        return 0.0

    pairs = sorted(zip(confidences, tp_flags), key=lambda x: -x[0])
    tp_cum = 0; fp_cum = 0
    precisions = []; recalls = []

    for _, tp in pairs:
        if tp:
            tp_cum += 1
        else:
            fp_cum += 1
        precisions.append(tp_cum / (tp_cum + fp_cum))
        recalls.append(tp_cum / n_gt)

    # 101-point interpolation
    ap = 0.0
    for t in [r / 100 for r in range(0, 101)]:
        p_at_t = max((p for r, p in zip(recalls, precisions) if r >= t), default=0.0)
        ap += p_at_t / 101
    return ap


def compute_metrics(
    gt: list[GTBox],
    preds: list[PredBox],
    conf_threshold: float,
) -> dict:
    """Compute per-class and macro precision, recall, F1, mAP@0.5, mAP@0.5:0.95."""

    # mAP@0.5
    matches_50, n_gt = _match_predictions(gt, preds, iou_threshold=0.50)

    per_class: dict[int, dict] = {}
    for cls_id in range(NUM_CLASSES):
        cls_name = CLASS_NAMES[cls_id]
        cls_matches = matches_50.get(cls_id, [])
        n_gt_cls = n_gt.get(cls_id, 0)
        n_pred_cls = len(cls_matches)

        if not cls_matches:
            per_class[cls_id] = {
                "class_name": cls_name, "n_gt": n_gt_cls, "n_pred": 0,
                "tp": 0, "fp": 0, "fn": n_gt_cls,
                "precision": 0.0, "recall": 0.0, "f1": 0.0, "ap50": 0.0,
            }
            continue

        confs = [c for c, _ in cls_matches]
        tps_  = [t for _, t in cls_matches]
        tp = sum(tps_); fp = n_pred_cls - tp; fn = max(n_gt_cls - tp, 0)
        precision = tp / max(tp + fp, 1)
        recall    = tp / max(n_gt_cls, 1)
        f1        = 2 * precision * recall / max(precision + recall, 1e-9)
        ap50      = _average_precision(confs, tps_, n_gt_cls)

        per_class[cls_id] = {
            "class_name": cls_name,
            "n_gt": n_gt_cls, "n_pred": n_pred_cls,
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4),
            "recall":    round(recall,    4),
            "f1":        round(f1,        4),
            "ap50":      round(ap50,      4),
        }

    # mAP@0.5:0.95
    aps_50_95: list[float] = []
    for iou_t in IOU_THRESHOLDS:
        matches_t, n_gt_t = _match_predictions(gt, preds, iou_threshold=iou_t)
        class_aps = []
        for cls_id in range(NUM_CLASSES):
            cls_m = matches_t.get(cls_id, [])
            n = n_gt_t.get(cls_id, 0)
            if not cls_m:
                class_aps.append(0.0)
                continue
            confs = [c for c, _ in cls_m]
            tps_  = [t for _, t in cls_m]
            class_aps.append(_average_precision(confs, tps_, n))
        aps_50_95.append(sum(class_aps) / NUM_CLASSES)

    map_50    = sum(pc["ap50"] for pc in per_class.values()) / NUM_CLASSES
    map_50_95 = sum(aps_50_95) / len(IOU_THRESHOLDS)

    # Macro-averaged P/R/F1
    macro_p  = sum(pc["precision"] for pc in per_class.values()) / NUM_CLASSES
    macro_r  = sum(pc["recall"]    for pc in per_class.values()) / NUM_CLASSES
    macro_f1 = sum(pc["f1"]        for pc in per_class.values()) / NUM_CLASSES

    return {
        "conf_threshold": conf_threshold,
        "macro": {
            "precision": round(macro_p,  4),
            "recall":    round(macro_r,  4),
            "f1":        round(macro_f1, 4),
            "mAP50":     round(map_50,   4),
            "mAP50_95":  round(map_50_95,4),
        },
        "per_class": {v["class_name"]: v for v in per_class.values()},
    }


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------

def build_confusion_matrix(
    gt: list[GTBox],
    preds: list[PredBox],
    iou_threshold: float = 0.50,
) -> np.ndarray:
    """
    Returns a (NUM_CLASSES+1, NUM_CLASSES+1) confusion matrix.
    Row = GT class (last row = background / missed).
    Col = Pred class (last col = false positive background).
    """
    n = NUM_CLASSES + 1   # +1 for background
    cm = np.zeros((n, n), dtype=np.int64)

    # Index GT
    gt_index: dict[str, list[list]] = defaultdict(list)
    for g in gt:
        gt_index[g.tile_id].append([g.class_id, g.box, False])

    sorted_preds = sorted(preds, key=lambda p: -p.confidence)

    for pred in sorted_preds:
        gts_in_tile = gt_index.get(pred.tile_id, [])
        best_iou = 0.0; best_gt_idx = -1; best_gt_cls = -1

        for idx, (gt_cls, gt_box, matched) in enumerate(gts_in_tile):
            if matched:
                continue
            iou = Box.iou(pred.box, gt_box)
            if iou > best_iou:
                best_iou = iou; best_gt_idx = idx; best_gt_cls = gt_cls

        if best_iou >= iou_threshold and best_gt_idx >= 0:
            gts_in_tile[best_gt_idx][2] = True
            cm[best_gt_cls][pred.class_id] += 1   # TP or confusion
        else:
            cm[NUM_CLASSES][pred.class_id] += 1   # FP (background predicted as class)

    # Missed detections: unmatched GT → background
    for gts in gt_index.values():
        for gt_cls, _, matched in gts:
            if not matched:
                cm[gt_cls][NUM_CLASSES] += 1   # FN

    return cm


def confusion_matrix_to_dict(cm: np.ndarray) -> dict:
    labels = [CLASS_NAMES[i] for i in range(NUM_CLASSES)] + ["background"]
    return {
        "labels": labels,
        "matrix": cm.tolist(),
    }


# ---------------------------------------------------------------------------
# Gallery (FP / FN visualisation)
# ---------------------------------------------------------------------------

def _tile_image(image_path: str | None, size: int = 320) -> "Image.Image | None":
    if not _PIL_AVAILABLE or not image_path:
        return None
    p = Path(image_path)
    if not p.exists():
        return None
    try:
        img = Image.open(p).convert("RGB").resize((size, size))
        return img
    except Exception:
        return None


def build_gallery(
    gt: list[GTBox],
    preds: list[PredBox],
    manifest_path: Path,
    out_dir: Path,
    split: str,
    iou_threshold: float = 0.50,
    max_fp: int = 50,
    max_fn: int = 50,
    thumb_size: int = 320,
) -> dict:
    """Save FP and FN gallery PNGs and return paths."""
    if not _PIL_AVAILABLE:
        return {"gallery_fp": None, "gallery_fn": None, "n_fp": 0, "n_fn": 0}

    # Load image paths from manifest
    tile_image_paths: dict[str, str] = {}
    with manifest_path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["split"] == split:
                tile_image_paths[rec["tile_id"]] = rec.get("image_path", "")

    # Identify FPs and FNs
    gt_index: dict[str, list[list]] = defaultdict(list)
    for g in gt:
        gt_index[g.tile_id].append([g.class_id, g.box, False])

    fps: list[dict] = []
    fns: list[dict] = []

    sorted_preds = sorted(preds, key=lambda p: -p.confidence)
    for pred in sorted_preds:
        gts = gt_index.get(pred.tile_id, [])
        best_iou = 0.0; best_idx = -1
        for idx, (gc, gb, matched) in enumerate(gts):
            if matched: continue
            iou = Box.iou(pred.box, gb)
            if iou > best_iou:
                best_iou = iou; best_idx = idx
        if best_iou >= iou_threshold and best_idx >= 0:
            gts[best_idx][2] = True
        else:
            fps.append({"tile_id": pred.tile_id, "class": CLASS_NAMES.get(pred.class_id, "?"),
                        "conf": pred.confidence, "box": pred.box})

    for tile_id, gts in gt_index.items():
        for gc, gb, matched in gts:
            if not matched:
                fns.append({"tile_id": tile_id, "class": CLASS_NAMES.get(gc, "?"), "box": gb})

    def _make_grid(entries: list[dict], label: str, out_path: Path, n_max: int) -> int:
        entries = entries[:n_max]
        if not entries:
            return 0
        cols = 5
        rows = math.ceil(len(entries) / cols)
        grid = Image.new("RGB", (cols * thumb_size, rows * thumb_size), (30, 30, 30))
        draw = ImageDraw.Draw(grid)
        for i, entry in enumerate(entries):
            img = _tile_image(tile_image_paths.get(entry["tile_id"]), thumb_size) or \
                  Image.new("RGB", (thumb_size, thumb_size), (60, 60, 60))
            x = (i % cols) * thumb_size
            y = (i // cols) * thumb_size
            grid.paste(img, (x, y))
            caption = f"{entry['class']}"
            if "conf" in entry:
                caption += f" {entry['conf']:.2f}"
            draw.rectangle([x, y, x + thumb_size - 1, y + 20], fill=(200, 50, 50))
            draw.text((x + 4, y + 3), caption, fill="white")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        grid.save(out_path)
        return len(entries)

    fp_path = out_dir / "gallery_false_positives.png"
    fn_path = out_dir / "gallery_missed_detections.png"
    n_fp = _make_grid(fps, "FP", fp_path, max_fp)
    n_fn = _make_grid(fns, "FN", fn_path, max_fn)

    return {
        "gallery_fp": str(fp_path) if n_fp else None,
        "gallery_fn": str(fn_path) if n_fn else None,
        "n_fp": len(fps),   # total before truncation
        "n_fn": len(fns),
    }


# ---------------------------------------------------------------------------
# JSON report builder
# ---------------------------------------------------------------------------

def build_report(
    metrics: dict,
    confusion: dict,
    latency: dict,
    gallery: dict,
    split: str,
    conf_threshold: float,
    manifest_path: str,
    preds_path: str,
) -> dict:
    """Assemble the JSON report consumed by the backend /v1/eval endpoint."""
    return {
        "schema_version": "1.0",
        "split":          split,
        "conf_threshold": conf_threshold,
        "manifest":       manifest_path,
        "predictions":    preds_path,
        "metrics":        metrics,
        "confusion_matrix": confusion,
        "latency":        latency,
        "gallery":        gallery,
        "calibration_discipline": {
            "val_reserved_for": "Platt-scaling confidence calibration after training",
            "test_policy":      "Hold-out benchmark — never used for threshold tuning",
            "current_split":    split,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate YOLO26 Nano predictions against AquaSense ground truth."
    )
    parser.add_argument("--manifest",   required=True, type=Path)
    parser.add_argument("--preds",      required=True, type=Path,
                        help="JSONL predictions file (one tile per line).")
    parser.add_argument("--split",      required=True, choices=["train", "val", "test"])
    parser.add_argument("--out-dir",    required=True, type=Path)
    parser.add_argument("--conf",       type=float, default=0.25,
                        help="Confidence threshold for evaluation (default: 0.25).")
    parser.add_argument("--iou",        type=float, default=0.50,
                        help="IoU matching threshold (default: 0.50).")
    parser.add_argument("--max-gallery", type=int, default=50,
                        help="Max FP/FN images in each gallery grid (default: 50).")
    parser.add_argument("--allow-test-eval", action="store_true",
                        help="Required flag to evaluate on test split.")
    args = parser.parse_args()

    # Calibration discipline guard
    if args.split == "test" and not args.allow_test_eval:
        print(
            "\n[GUARD] You are attempting to evaluate on the TEST split.\n"
            "        The test split is the held-out final benchmark.\n"
            "        Use --split val for threshold tuning and calibration.\n"
            "        If you truly mean to run the final evaluation, pass --allow-test-eval.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.split == "test" and args.allow_test_eval:
        print(
            "\n[WARNING] *** FINAL TEST EVALUATION — results will be used for benchmarking ***\n"
            "          Confirm you are NOT using these numbers to tune the confidence threshold.\n",
            file=sys.stderr,
        )

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[eval] Loading ground truth from manifest ({args.split} split)…")
    t0 = time.perf_counter()
    gt = load_ground_truth(args.manifest.resolve(), args.split)
    print(f"[eval]   {len(gt)} GT boxes loaded in {time.perf_counter()-t0:.2f}s")

    print(f"[eval] Loading predictions (conf ≥ {args.conf})…")
    preds, latency_stats = load_predictions(args.preds.resolve(), args.conf)
    print(f"[eval]   {len(preds)} predictions loaded")

    print("[eval] Computing metrics…")
    metrics = compute_metrics(gt, preds, args.conf)
    _print_metrics(metrics)

    print("[eval] Building confusion matrix…")
    cm = build_confusion_matrix(gt, preds, iou_threshold=args.iou)
    confusion = confusion_matrix_to_dict(cm)
    _print_confusion(cm, confusion["labels"])

    print("[eval] Building FP/FN gallery…")
    gallery = build_gallery(
        gt, preds,
        manifest_path=args.manifest.resolve(),
        out_dir=out_dir,
        split=args.split,
        iou_threshold=args.iou,
        max_fp=args.max_gallery,
        max_fn=args.max_gallery,
    )
    if gallery["gallery_fp"]:
        print(f"[eval]   FP gallery → {gallery['gallery_fp']}  ({gallery['n_fp']} total FPs)")
    if gallery["gallery_fn"]:
        print(f"[eval]   FN gallery → {gallery['gallery_fn']}  ({gallery['n_fn']} total FNs)")

    print("[eval] Latency stats:")
    _print_latency(latency_stats)

    report = build_report(
        metrics=metrics,
        confusion=confusion,
        latency=latency_stats,
        gallery=gallery,
        split=args.split,
        conf_threshold=args.conf,
        manifest_path=str(args.manifest.resolve()),
        preds_path=str(args.preds.resolve()),
    )

    report_path = out_dir / "eval_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[eval] Report → {report_path}")

    # Also write a slim summary for the backend health / UI
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps({
            "split": args.split,
            "conf_threshold": args.conf,
            "macro": metrics["macro"],
            "n_gt":  len(gt),
            "n_pred": len(preds),
            "n_fp":  gallery["n_fp"],
            "n_fn":  gallery["n_fn"],
            "tile_latency_p95_ms": latency_stats["tile_latency"]["p95_ms"],
            "mission_latency_p95_ms": latency_stats["mission_latency"]["p95_ms"],
        }, indent=2),
        encoding="utf-8",
    )
    print(f"[eval] Summary → {summary_path}")


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def _print_metrics(metrics: dict) -> None:
    m = metrics["macro"]
    print(f"\n{'─'*60}")
    print(f"  Macro  P={m['precision']:.4f}  R={m['recall']:.4f}  "
          f"F1={m['f1']:.4f}  mAP50={m['mAP50']:.4f}  mAP50-95={m['mAP50_95']:.4f}")
    print(f"{'─'*60}")
    fmt = "  {:<35s}  P={:.3f}  R={:.3f}  F1={:.3f}  AP50={:.3f}"
    for cls_name, pc in metrics["per_class"].items():
        print(fmt.format(cls_name, pc["precision"], pc["recall"], pc["f1"], pc["ap50"]))
    print(f"{'─'*60}\n")


def _print_confusion(cm: np.ndarray, labels: list[str]) -> None:
    print("\nConfusion Matrix (rows=GT, cols=Pred):")
    w = 6
    header = " " * 28 + "".join(f"{l[:5]:>{w}}" for l in labels)
    print(header)
    for i, row_label in enumerate(labels):
        row = f"  {row_label[:26]:<26}  " + "".join(f"{cm[i,j]:>{w}d}" for j in range(len(labels)))
        print(row)
    print()


def _print_latency(stats: dict) -> None:
    tl = stats["tile_latency"]
    ml = stats["mission_latency"]
    if tl["n"]:
        print(f"  Tile latency     n={tl['n']}  mean={tl['mean_ms']}ms  "
              f"p50={tl['p50_ms']}ms  p95={tl['p95_ms']}ms  p99={tl['p99_ms']}ms")
    else:
        print("  Tile latency     (no data in predictions file)")
    if ml["n"]:
        print(f"  Mission latency  n={ml['n']}  mean={ml['mean_ms']}ms  "
              f"p50={ml['p50_ms']}ms  p95={ml['p95_ms']}ms  p99={ml['p99_ms']}ms")
    else:
        print("  Mission latency  (no data in predictions file)")


if __name__ == "__main__":
    main()
