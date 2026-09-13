#!/usr/bin/env python3
"""
build_manifest.py — AquaSense Sonar Tile Label Manifest Builder
================================================================
PS 26057 | SIH 2026

Walks the YOLO dataset directory layout (images/{train,val,test} +
labels/{train,val,test}) and emits a JSON Lines manifest where each
line is one tile record:

    {
        "tile_id":       "train__SeabedObjects__wreck_001__0",
        "split":         "train",
        "mission":       "SeabedObjects",           # directory name = mission key
        "source_file":   "data/.../wreck_001.png",  # relative to dataset root
        "image_path":    "images/train/wreck_001.png",
        "label_path":    "labels/train/wreck_001.txt",
        "source_xtf":    null,                      # filled when --xtf-meta is given
        "ping_start":    null,
        "ping_end":      null,
        "width_px":      640,
        "height_px":     640,
        "annotations": [
            {
                "ann_id":    "train__SeabedObjects__wreck_001__0__ann0",
                "class_id":  0,
                "class_name": "human_artifact_wreck",
                "box_cx_norm": 0.512,
                "box_cy_norm": 0.380,
                "box_w_norm":  0.240,
                "box_h_norm":  0.198,
                "has_mask":   false,
                "mask_points": null
            }
        ]
    }

When --xtf-meta path/to/xtf_metadata.json is provided the script joins
the per-ping navigation JSON produced by extract_xtf() and populates
source_xtf, ping_start, and ping_end from the tile filename convention
<mission>_ping<start>_<end>_<col>.png.

Usage
-----
    python evaluation/build_manifest.py \\
        --dataset  data/yolo_sonar_dataset \\
        --out      evaluation/manifest.jsonl \\
        [--xtf-meta  path/to/xtf_metadata.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------------------
# 6-class taxonomy (must match configs/sonar_debris_yolo26.yaml)
# ---------------------------------------------------------------------------
CLASS_NAMES: dict[int, str] = {
    0: "human_artifact_wreck",
    1: "electrical_cable",
    2: "electronic_hazard",
    3: "plastic_debris",
    4: "metal_drum_scrap",
    5: "biological_geological_exclusion",
}

# Tile filename convention for XTF-tiled images:
#   <mission>_ping<start>_<end>_col<col>.png
_PING_RE = re.compile(r"ping(\d+)_(\d+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mission_from_path(image_path: Path, split_root: Path) -> str:
    """Infer mission name from the first subdirectory below split_root."""
    try:
        rel = image_path.relative_to(split_root)
        parts = rel.parts
        return parts[0] if len(parts) > 1 else "unknown"
    except ValueError:
        return image_path.stem.split("_")[0]


def _read_label_file(label_path: Path) -> list[dict]:
    """Parse a YOLO-format label file into a list of annotation dicts."""
    annotations: list[dict] = []
    if not label_path.exists():
        return annotations
    with label_path.open() as fh:
        for line in fh:
            parts = line.strip().split()
            if not parts:
                continue
            try:
                cls_id = int(parts[0])
                cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            except (ValueError, IndexError):
                continue
            # YOLO Seg format: class cx cy x1 y1 x2 y2 ...
            has_mask = len(parts) > 5
            mask_pts: list[tuple[float, float]] | None = None
            if has_mask:
                coords = [float(v) for v in parts[5:]]
                mask_pts = list(zip(coords[0::2], coords[1::2]))
            annotations.append({
                "class_id":    cls_id,
                "class_name":  CLASS_NAMES.get(cls_id, f"unknown_{cls_id}"),
                "box_cx_norm": round(cx, 6),
                "box_cy_norm": round(cy, 6),
                "box_w_norm":  round(w, 6),
                "box_h_norm":  round(h, 6),
                "has_mask":    has_mask,
                "mask_points": mask_pts,
            })
    return annotations


def _image_size(image_path: Path) -> tuple[int, int]:
    """Return (width_px, height_px) without decoding the full image."""
    try:
        with Image.open(image_path) as img:
            return img.size   # (width, height)
    except Exception:
        return 640, 640       # safe default for corrupt files


def _ping_range_from_filename(stem: str) -> tuple[int | None, int | None]:
    m = _PING_RE.search(stem)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_manifest(
    dataset_root: Path,
    out_path: Path,
    xtf_meta_path: Path | None,
) -> int:
    """Write manifest JSONL and return the total number of records written."""
    # Optional XTF metadata for ping provenance
    xtf_meta: dict = {}
    if xtf_meta_path and xtf_meta_path.exists():
        with xtf_meta_path.open() as fh:
            raw = json.load(fh)
        # Accept either a single survey dict or a {mission: dict} mapping
        if "ping_count" in raw:
            xtf_meta = {"default": raw}
        else:
            xtf_meta = raw

    splits = ["train", "val", "test"]
    records_written = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as out_fh:
        for split in splits:
            img_dir   = dataset_root / "images" / split
            label_dir = dataset_root / "labels" / split
            if not img_dir.exists():
                continue

            img_files = sorted(
                p for p in img_dir.rglob("*")
                if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            )
            for img_path in img_files:
                # Locate matching label
                rel_from_split = img_path.relative_to(img_dir)
                label_path = label_dir / rel_from_split.with_suffix(".txt")

                # Mission key = first path component after the split dir
                mission = _mission_from_path(img_path, img_dir)

                # XTF provenance
                ping_start, ping_end = _ping_range_from_filename(img_path.stem)
                source_xtf: str | None = None
                if xtf_meta:
                    meta_entry = xtf_meta.get(mission) or xtf_meta.get("default")
                    if meta_entry:
                        source_xtf = meta_entry.get("metadata_path")

                width_px, height_px = _image_size(img_path)
                raw_anns = _read_label_file(label_path)
                tile_id = f"{split}__{mission}__{img_path.stem}"

                # Build per-annotation IDs
                annotations = []
                for i, ann in enumerate(raw_anns):
                    annotations.append({
                        "ann_id":      f"{tile_id}__ann{i}",
                        **ann,
                    })

                record = {
                    "tile_id":      tile_id,
                    "split":        split,
                    "mission":      mission,
                    "source_file":  str(img_path.relative_to(dataset_root)),
                    "image_path":   str(img_path),
                    "label_path":   str(label_path) if label_path.exists() else None,
                    "source_xtf":   source_xtf,
                    "ping_start":   ping_start,
                    "ping_end":     ping_end,
                    "width_px":     width_px,
                    "height_px":    height_px,
                    "annotations":  annotations,
                }
                out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                records_written += 1

    return records_written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a JSONL tile-label manifest from a YOLO dataset directory."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Root of the YOLO dataset (contains images/ and labels/).",
    )
    parser.add_argument(
        "--out",
        default="evaluation/manifest.jsonl",
        type=Path,
        help="Output path for the JSONL manifest.",
    )
    parser.add_argument(
        "--xtf-meta",
        default=None,
        type=Path,
        dest="xtf_meta",
        help="Optional path to xtf_metadata.json (or a dict of mission→metadata) "
             "for XTF ping provenance.",
    )
    args = parser.parse_args()

    dataset_root = args.dataset.resolve()
    if not dataset_root.exists():
        print(f"[ERROR] Dataset root not found: {dataset_root}", file=sys.stderr)
        sys.exit(1)

    print(f"[manifest] Scanning dataset: {dataset_root}")
    n = build_manifest(dataset_root, args.out.resolve(), args.xtf_meta)
    print(f"[manifest] Written {n} tile records → {args.out.resolve()}")


if __name__ == "__main__":
    main()
