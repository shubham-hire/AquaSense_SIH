#!/usr/bin/env python3
"""
calibrate.py — AquaSense Calibration Input Collection & Platt Scaling Fitter
===========================================================================
PS 26057 | SIH 2026

Collects raw model confidence scores paired with empirical ground-truth outcomes
(True Positive: y=1, False Positive: y=0) from validation set evaluations,
and fits Platt scaling parameters (logistic calibration):

    P(y = 1 | score) = 1 / (1 + exp(A * score + B))

Key features:
1. Input Collection:
   - Matches predicted bounding boxes against ground-truth boxes at IoU >= 0.50.
   - Saves fine-grained raw calibration samples to calibration_samples.jsonl.
2. Platt Scaling:
   - Fits both global and per-class logistic calibration parameters (A, B).
   - Computes Expected Calibration Error (ECE) across M=10 confidence bins before
     and after calibration.
   - Computes Brier score reduction.
   - Exports fitted parameters to platt_scales.json for direct use in
     backend/app/detector.py.
3. Pre-training readiness:
   - Can synthesize realistic calibration data for offline dry-runs and pipeline
     validation before final weights arrive.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from evaluate import Box, GTBox, PredBox, load_ground_truth, load_predictions

DEFAULT_CLASSES = {
    0: "human_artifact_wreck",
    1: "electrical_cable",
    2: "electronic_hazard",
    3: "plastic_debris",
    4: "metal_drum_scrap",
    5: "biological_geological_exclusion",
    6: "ghost_gear",
}


def collect_calibration_samples(
    gt: list[GTBox],
    preds: list[PredBox],
    iou_threshold: float = 0.50,
    class_names: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Pairs each predicted box with binary outcome y in {0, 1}:
      y = 1 if matches GT box of same class at IoU >= iou_threshold
      y = 0 otherwise (false positive)
    """
    classes = class_names if class_names is not None else DEFAULT_CLASSES

    # Index GT by (tile_id, class_id)
    gt_index: dict[tuple[str, int], list[tuple[GTBox, bool]]] = defaultdict(list)
    for g in gt:
        gt_index[(g.tile_id, g.class_id)].append((g, False))

    samples: list[dict[str, Any]] = []

    # Sort predictions descending by confidence
    sorted_preds = sorted(preds, key=lambda p: -p.confidence)

    for pred in sorted_preds:
        key = (pred.tile_id, pred.class_id)
        gt_list = gt_index.get(key, [])

        best_iou = 0.0
        best_idx = -1

        for idx, (g, matched) in enumerate(gt_list):
            if matched:
                continue
            iou = Box.iou(pred.box, g.box)
            if iou > best_iou:
                best_iou = iou
                best_idx = idx

        # True positive if IoU matches threshold and GT not already claimed
        if best_iou >= iou_threshold and best_idx >= 0:
            gt_list[best_idx] = (gt_list[best_idx][0], True)
            label = 1
        else:
            label = 0

        conf = float(np.clip(pred.confidence, 1e-6, 1.0 - 1e-6))
        logit = float(math.log(conf / (1.0 - conf)))

        samples.append({
            "tile_id": pred.tile_id,
            "mission": pred.mission,
            "class_id": pred.class_id,
            "class_name": classes.get(pred.class_id, f"class_{pred.class_id}"),
            "raw_confidence": round(conf, 5),
            "raw_logit": round(logit, 5),
            "target_label": label,
            "best_iou": round(best_iou, 4),
            "box": list(pred.box.to_xyxy()),
        })

    return samples


def generate_synthetic_calibration_samples(
    n_samples: int = 400,
    class_names: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Generates synthetic uncalibrated samples for dry-run before training weights arrive."""
    classes = class_names if class_names is not None else DEFAULT_CLASSES
    samples = []
    np.random.seed(42)

    for i in range(n_samples):
        cid = int(np.random.choice(list(classes.keys())))
        # Simulate typical overconfident detector (raw conf higher than true probability)
        true_prob = float(np.random.beta(2.0, 1.5))
        # Overconfidence distortion
        raw_conf = float(np.clip(true_prob ** 0.65 + np.random.normal(0, 0.08), 0.05, 0.98))
        label = 1 if np.random.rand() < true_prob else 0
        logit = float(math.log(raw_conf / (1.0 - raw_conf)))

        samples.append({
            "tile_id": f"sim_tile_{i:04d}",
            "mission": "SyntheticCalibration",
            "class_id": cid,
            "class_name": classes.get(cid, f"class_{cid}"),
            "raw_confidence": round(raw_conf, 5),
            "raw_logit": round(logit, 5),
            "target_label": label,
            "best_iou": round(0.65 if label == 1 else 0.20, 4),
            "box": [0.2, 0.2, 0.6, 0.6],
        })
    return samples


def fit_platt_parameters(confidences: list[float], labels: list[int]) -> tuple[float, float]:
    """
    Fits logistic regression parameters (A, B) using log-loss minimization:
        P(y = 1 | s) = 1 / (1 + exp(A * s + B))
    Returns (A, B).
    """
    from scipy.optimize import minimize
    from scipy.special import expit

    s = np.array(confidences, dtype=np.float64)
    y = np.array(labels, dtype=np.float64)

    if len(s) < 5 or len(np.unique(y)) < 2:
        return -1.0, 0.0

    # Platt (1999) smoothed targets to avoid overconfidence at boundaries
    n_pos = np.sum(y == 1)
    n_neg = np.sum(y == 0)
    t_pos = (n_pos + 1.0) / (n_pos + 2.0)
    t_neg = 1.0 / (n_neg + 2.0)
    targets = np.where(y == 1, t_pos, t_neg)

    def loss(params: np.ndarray) -> float:
        A, B = params[0], params[1]
        # P(y=1|s) = 1 / (1 + exp(A*s + B)) = expit(-(A*s + B))
        f = -(A * s + B)
        p = np.clip(expit(f), 1e-12, 1.0 - 1e-12)
        # Binary cross-entropy with smoothed targets
        bce = -np.mean(targets * np.log(p) + (1.0 - targets) * np.log(1.0 - p))
        # Mild L2 regularization on A and B
        reg = 1e-4 * (A * A + B * B)
        return float(bce + reg)

    # Initial guess: A ~ -3.0 (higher conf -> lower (A*s+B) -> higher P), B ~ 0.0
    res = minimize(loss, x0=[-3.0, 0.0], method="L-BFGS-B")
    A_opt, B_opt = float(res.x[0]), float(res.x[1])
    return A_opt, B_opt


def apply_platt(s: float, A: float, B: float) -> float:
    """Applies Platt parameters to an uncalibrated score."""
    from scipy.special import expit
    return float(expit(-(A * s + B)))


def compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> dict[str, Any]:
    """
    Computes Expected Calibration Error (ECE) and bin reliability statistics.
    ECE = sum_{m=1}^M (|B_m| / N) * |acc(B_m) - conf(B_m)|
    """
    if not probs:
        return {"ece": 0.0, "bins": []}

    p = np.array(probs)
    y = np.array(labels)
    n = len(p)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_details = []
    ece = 0.0

    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        mask = (p >= low) & (p <= high) if i == n_bins - 1 else (p >= low) & (p < high)
        count = int(np.sum(mask))
        if count > 0:
            bin_conf = float(np.mean(p[mask]))
            bin_acc = float(np.mean(y[mask]))
            diff = abs(bin_acc - bin_conf)
            ece += (count / n) * diff
            bin_details.append({
                "bin_range": [round(low, 2), round(high, 2)],
                "count": count,
                "confidence": round(bin_conf, 4),
                "accuracy": round(bin_acc, 4),
                "error": round(diff, 4),
            })
        else:
            bin_details.append({
                "bin_range": [round(low, 2), round(high, 2)],
                "count": 0,
                "confidence": round((low + high) / 2, 4),
                "accuracy": 0.0,
                "error": 0.0,
            })

    # Brier score: mean squared difference
    brier = float(np.mean((p - y) ** 2))

    return {
        "ece": round(float(ece), 4),
        "brier_score": round(brier, 4),
        "bins": bin_details,
    }


def fit_and_export_calibration(
    samples: list[dict[str, Any]],
    out_dir: Path,
    class_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Fits global and per-class Platt scalers, evaluates ECE, and writes platt_scales.json."""
    classes = class_names if class_names is not None else DEFAULT_CLASSES
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save raw calibration samples
    samples_path = out_dir / "calibration_samples.jsonl"
    with samples_path.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")

    all_scores = [s["raw_confidence"] for s in samples]
    all_labels = [s["target_label"] for s in samples]

    # Global Fit
    global_A, global_B = fit_platt_parameters(all_scores, all_labels)
    global_calibrated = [apply_platt(s, global_A, global_B) for s in all_scores]

    raw_ece = compute_ece(all_scores, all_labels)
    cal_ece = compute_ece(global_calibrated, all_labels)

    # Per-class fits
    per_class_models: dict[str, Any] = {}
    class_samples: dict[int, list[dict]] = defaultdict(list)
    for s in samples:
        class_samples[s["class_id"]].append(s)

    for cid, cname in classes.items():
        c_samples = class_samples.get(cid, [])
        if len(c_samples) >= 10:
            c_scores = [cs["raw_confidence"] for cs in c_samples]
            c_labels = [cs["target_label"] for cs in c_samples]
            cA, cB = fit_platt_parameters(c_scores, c_labels)
            c_cal = [apply_platt(cs, cA, cB) for cs in c_scores]
            per_class_models[cname] = {
                "class_id": cid,
                "n_samples": len(c_samples),
                "platt_A": round(cA, 5),
                "platt_B": round(cB, 5),
                "raw_ece": compute_ece(c_scores, c_labels)["ece"],
                "calibrated_ece": compute_ece(c_cal, c_labels)["ece"],
            }
        else:
            per_class_models[cname] = {
                "class_id": cid,
                "n_samples": len(c_samples),
                "platt_A": round(global_A, 5),
                "platt_B": round(global_B, 5),
                "note": "Fell back to global model due to low sample count",
                "raw_ece": None,
                "calibrated_ece": None,
            }

    calibration_ledger = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_calibration_samples": len(samples),
        "global_model": {
            "platt_A": round(global_A, 5),
            "platt_B": round(global_B, 5),
            "formula": "P(target=1 | conf) = 1 / (1 + exp(A * conf + B))",
            "metrics": {
                "uncalibrated_ece": raw_ece["ece"],
                "calibrated_ece": cal_ece["ece"],
                "ece_improvement_pct": round((raw_ece["ece"] - cal_ece["ece"]) / max(raw_ece["ece"], 1e-4) * 100, 2),
                "uncalibrated_brier": raw_ece["brier_score"],
                "calibrated_brier": cal_ece["brier_score"],
            },
        },
        "per_class_models": per_class_models,
        "calibration_bins": cal_ece["bins"],
    }

    scales_path = out_dir / "platt_scales.json"
    scales_path.write_text(json.dumps(calibration_ledger, indent=2), encoding="utf-8")

    return {
        "ledger": calibration_ledger,
        "samples_path": samples_path,
        "scales_path": scales_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AquaSense Calibration Input Collector & Platt Scaling Fitter"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to manifest.jsonl (contains ground truth for --split val)",
    )
    parser.add_argument(
        "--preds",
        type=Path,
        default=None,
        help="Path to predictions JSONL from evaluation runner",
    )
    parser.add_argument(
        "--split",
        default="val",
        choices=["val", "train"],
        help="Dataset split for calibration (default: val). Never calibrate on test!",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("evaluation/reports/calibration"),
        help="Directory to save calibration samples and fitted parameters",
    )
    parser.add_argument(
        "--synthetic-dry-run",
        action="store_true",
        help="Generate synthetic calibration samples if weights are not trained yet",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("  AQUASENSE: CALIBRATION & PLATT SCALING FITTER")
    print("=" * 65)

    if args.synthetic_dry_run or not (args.manifest and args.preds and args.manifest.exists() and args.preds.exists()):
        print("[*] Running synthetic dry-run (pre-training mode)...")
        samples = generate_synthetic_calibration_samples(n_samples=500)
    else:
        print(f"[*] Extracting calibration samples from: {args.preds} against {args.manifest}")
        gt = load_ground_truth(args.manifest.resolve(), args.split)
        preds, _ = load_predictions(args.preds.resolve(), conf_threshold=0.05)
        samples = collect_calibration_samples(gt, preds)

    print(f"[*] Collected {len(samples)} calibration samples.")
    result = fit_and_export_calibration(samples, args.out_dir)

    glob_m = result["ledger"]["global_model"]
    metrics = glob_m["metrics"]
    print("\n--- Platt Scaling Results ---")
    print(f"  Platt A (slope)       : {glob_m['platt_A']}")
    print(f"  Platt B (intercept)   : {glob_m['platt_B']}")
    print(f"  Uncalibrated ECE      : {metrics['uncalibrated_ece']:.4f}")
    print(f"  Calibrated ECE        : {metrics['calibrated_ece']:.4f}")
    print(f"  ECE Reduction         : {metrics['ece_improvement_pct']}%")
    print(f"  Brier Score           : {metrics['uncalibrated_brier']:.4f} -> {metrics['calibrated_brier']:.4f}")
    print(f"\n[PASS] Calibration parameters written to: {result['scales_path']}")


if __name__ == "__main__":
    main()
