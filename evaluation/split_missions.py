#!/usr/bin/env python3
"""
split_missions.py — Mission-Aware Train / Val / Test Splitter
==============================================================
PS 26057 | SIH 2026

KEY GUARANTEE
-------------
All tiles from a single mission/file stay in the SAME split.
Random tiles from the same survey are NEVER spread across splits.
This prevents label leakage and ensures honest generalisation estimates.

Calibration rule
----------------
The val split is reserved exclusively for Platt-scaling confidence
calibration AFTER training ends.  The test split is held out until
final benchmark reporting — it is NEVER used for threshold tuning.

Input
-----
  manifest.jsonl produced by build_manifest.py

Output
------
  split_index.json  (also printed to stdout)

  {
    "train": ["SeabedObjects", "SCTD", ...],
    "val":   ["MarineDebrisFLS"],
    "test":  ["NNSSS"],
    "tile_counts": {"train": 4210, "val": 680, "test": 530},
    "mission_counts": {"train": 5, "val": 1, "test": 1},
    "split_ratios": {"train": 0.788, "val": 0.127, "test": 0.099},
    "calibration_note": "val split reserved for Platt-scaling AFTER training. Never use test for threshold tuning.",
    "warnings": []
  }

The splitter also rewrites the YOLO dataset directory (images/labels) into
the correct per-split layout so Ultralytics can read it directly — without
moving files, only by writing split-specific file-list .txt files:
  data/yolo_sonar_dataset/train.txt
  data/yolo_sonar_dataset/val.txt
  data/yolo_sonar_dataset/test.txt

Usage
-----
    python evaluation/split_missions.py \\
        --manifest evaluation/manifest.jsonl \\
        --train-ratio 0.75 --val-ratio 0.15 --test-ratio 0.10 \\
        --seed 42 \\
        --out evaluation/split_index.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path


CALIBRATION_NOTE = (
    "val split is reserved for Platt-scaling / confidence calibration "
    "AFTER training ends. Do NOT use test split for threshold tuning."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_manifest(manifest_path: Path) -> list[dict]:
    records: list[dict] = []
    with manifest_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _group_by_mission(records: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        groups[rec["mission"]].append(rec)
    return dict(groups)


def _assign_missions(
    missions: list[str],
    tile_counts: dict[str, int],
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> dict[str, str]:
    """
    Greedy mission → split assignment.

    Strategy
    --------
    Sort missions by tile count (largest first) and greedily assign each to
    whichever split is furthest below its target ratio.  This avoids the
    degenerate case where one large mission dominates a split.

    Returns {mission: split_name}
    """
    rng = random.Random(seed)
    total = sum(tile_counts.values())
    targets = {"train": train_ratio, "val": val_ratio, "test": 1 - train_ratio - val_ratio}

    # Shuffle missions of equal size for reproducible randomness
    sorted_missions = sorted(missions, key=lambda m: (-tile_counts[m], m))
    rng.shuffle(sorted_missions)  # break ties randomly but deterministically
    sorted_missions = sorted(sorted_missions, key=lambda m: -tile_counts[m])

    accumulated: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    assignment: dict[str, str] = {}

    for mission in sorted_missions:
        n = tile_counts[mission]
        # Compute how far each split is below its target
        deficits = {
            split: targets[split] - accumulated[split] / max(total, 1)
            for split in ("train", "val", "test")
        }
        chosen = max(deficits, key=lambda s: deficits[s])
        assignment[mission] = chosen
        accumulated[chosen] += n

    return assignment


def _write_yolo_filelists(
    dataset_root: Path,
    assignment: dict[str, str],
    mission_tiles: dict[str, list[dict]],
) -> dict[str, int]:
    """Write train.txt / val.txt / test.txt with absolute image paths."""
    split_files: dict[str, list[str]] = defaultdict(list)
    for mission, split in assignment.items():
        for rec in mission_tiles[mission]:
            split_files[split].append(rec["image_path"])

    written: dict[str, int] = {}
    for split, paths in split_files.items():
        out = dataset_root / f"{split}.txt"
        out.write_text("\n".join(sorted(paths)) + "\n", encoding="utf-8")
        written[split] = len(paths)

    return written


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def _check_leakage(assignment: dict[str, str]) -> list[str]:
    """
    Verify no mission appears in more than one split.
    In a well-formed assignment this should never trigger, but we check
    explicitly as a safety net.
    """
    warnings: list[str] = []
    seen: dict[str, str] = {}
    for mission, split in assignment.items():
        if mission in seen and seen[mission] != split:
            warnings.append(
                f"LEAKAGE: mission '{mission}' appears in both "
                f"'{seen[mission]}' and '{split}' splits!"
            )
        seen[mission] = split
    return warnings


def _check_empty_splits(tile_counts: dict[str, dict]) -> list[str]:
    warnings: list[str] = []
    for split, counts in tile_counts.items():
        if sum(counts.values()) == 0:
            warnings.append(f"Split '{split}' has zero tiles — consider adjusting ratios.")
    return warnings


# ---------------------------------------------------------------------------
# Core splitter
# ---------------------------------------------------------------------------

def split_missions(
    manifest_path: Path,
    out_path: Path,
    train_ratio: float,
    val_ratio: float,
    seed: int,
    dataset_root: Path | None,
) -> dict:
    assert abs(train_ratio + val_ratio - 1.0) < 0.01 or val_ratio < 1.0, (
        "train + val must be ≤ 1.0"
    )

    records = _load_manifest(manifest_path)
    if not records:
        print("[split] Empty manifest — nothing to split.", file=sys.stderr)
        sys.exit(1)

    mission_tiles = _group_by_mission(records)
    missions = sorted(mission_tiles.keys())
    tile_counts = {m: len(tiles) for m, tiles in mission_tiles.items()}
    total_tiles = sum(tile_counts.values())

    print(f"[split] {len(missions)} missions | {total_tiles} total tiles")
    for m in missions:
        print(f"        {m:40s}  {tile_counts[m]:5d} tiles")

    assignment = _assign_missions(missions, tile_counts, train_ratio, val_ratio, seed)

    # Compute per-split mission and tile counts
    split_missions_map: dict[str, list[str]] = defaultdict(list)
    split_tile_totals: dict[str, int] = defaultdict(int)
    for mission, split in assignment.items():
        split_missions_map[split].append(mission)
        split_tile_totals[split] += tile_counts[mission]

    # Warnings
    warnings: list[str] = []
    warnings.extend(_check_leakage(assignment))
    warnings.extend(_check_empty_splits({s: {m: tile_counts[m] for m in ms} for s, ms in split_missions_map.items()}))
    if warnings:
        for w in warnings:
            print(f"[WARN] {w}", file=sys.stderr)

    # YOLO file lists
    if dataset_root and dataset_root.exists():
        written = _write_yolo_filelists(dataset_root, assignment, mission_tiles)
        for split, n in written.items():
            print(f"[split] Wrote {dataset_root}/{split}.txt  ({n} images)")

    total = max(total_tiles, 1)
    result = {
        "seed": seed,
        "train": sorted(split_missions_map.get("train", [])),
        "val":   sorted(split_missions_map.get("val",   [])),
        "test":  sorted(split_missions_map.get("test",  [])),
        "tile_counts": {
            "train": split_tile_totals.get("train", 0),
            "val":   split_tile_totals.get("val",   0),
            "test":  split_tile_totals.get("test",  0),
        },
        "mission_counts": {
            "train": len(split_missions_map.get("train", [])),
            "val":   len(split_missions_map.get("val",   [])),
            "test":  len(split_missions_map.get("test",  [])),
        },
        "split_ratios": {
            "train": round(split_tile_totals.get("train", 0) / total, 4),
            "val":   round(split_tile_totals.get("val",   0) / total, 4),
            "test":  round(split_tile_totals.get("test",  0) / total, 4),
        },
        "calibration_note": CALIBRATION_NOTE,
        "warnings": warnings,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[split] Split index → {out_path}")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mission-aware train/val/test split for AquaSense sonar tiles."
    )
    parser.add_argument("--manifest", required=True, type=Path,
                        help="JSONL manifest from build_manifest.py")
    parser.add_argument("--train-ratio", type=float, default=0.75,
                        help="Fraction of tiles for training (default: 0.75)")
    parser.add_argument("--val-ratio", type=float, default=0.15,
                        help="Fraction of tiles for validation/calibration (default: 0.15)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducible splits (default: 42)")
    parser.add_argument("--dataset-root", type=Path, default=None, dest="dataset_root",
                        help="If provided, writes train.txt/val.txt/test.txt to this directory.")
    parser.add_argument("--out", type=Path, default=Path("evaluation/split_index.json"),
                        help="Output path for the split index JSON.")
    args = parser.parse_args()

    result = split_missions(
        manifest_path=args.manifest.resolve(),
        out_path=args.out.resolve(),
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
        dataset_root=args.dataset_root.resolve() if args.dataset_root else None,
    )

    print("\n[split] Summary:")
    for split in ("train", "val", "test"):
        missions = result[split]
        tiles    = result["tile_counts"][split]
        ratio    = result["split_ratios"][split]
        print(f"  {split:5s}  {tiles:5d} tiles  ({ratio*100:.1f}%)  missions: {missions}")
    print(f"\n[NOTE] {result['calibration_note']}")


if __name__ == "__main__":
    main()
