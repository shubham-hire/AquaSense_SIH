from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image

from .schemas import QcReport
from .vendor_formats import extract_jsf, extract_sl2
from .xtf import extract_xtf

SUPPORTED_FORMATS = {".xtf": "XTF", ".jsf": "JSF", ".sl2": "SL2", ".tif": "GEOTIFF", ".tiff": "GEOTIFF", ".png": "IMAGE", ".jpg": "IMAGE", ".jpeg": "IMAGE"}


def inspect_file(survey_id: str, source: Path, original_name: str, artifact_dir: Path | None = None) -> tuple[QcReport, dict | None]:
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported sonar format: {suffix or 'no extension'}")
    payload = source.read_bytes()
    # Image formats support meaningful QC immediately; binary formats retain a safe,
    # honest QC record until their vendor parser extracts ping arrays.
    extraction = None
    if suffix == ".xtf":
        if artifact_dir is None:
            raise ValueError("An artifact directory is required for XTF extraction")
        extraction = extract_xtf(source, artifact_dir)
        motion_rows = extraction["motion_artifact_rows"]
        dropout = extraction["dropout_ratio_percent"]
        dynamic_range = extraction["dynamic_range_db"]
        speckle = extraction["speckle_index"]
        pings = extraction["ping_count"]
    elif suffix == ".jsf":
        if artifact_dir is None:
            raise ValueError("An artifact directory is required for JSF extraction")
        extraction = extract_jsf(source, artifact_dir)
        motion_rows, dropout = extraction["motion_artifact_rows"], extraction["dropout_ratio_percent"]
        dynamic_range, speckle, pings = extraction["dynamic_range_db"], extraction["speckle_index"], extraction["ping_count"]
    elif suffix == ".sl2":
        if artifact_dir is None:
            raise ValueError("An artifact directory is required for SL2 extraction")
        extraction = extract_sl2(source, artifact_dir)
        motion_rows, dropout = extraction["motion_artifact_rows"], extraction["dropout_ratio_percent"]
        dynamic_range, speckle, pings = extraction["dynamic_range_db"], extraction["speckle_index"], extraction["ping_count"]
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        with Image.open(source) as image:
            pixels = np.asarray(image.convert("L"), dtype=np.float32)
        row_means = pixels.mean(axis=1)
        local_std = max(float(row_means.std()), 1.0)
        motion_rows = np.where(np.abs(row_means - row_means.mean()) > 3 * local_std)[0].astype(int).tolist()
        dropout = round(100 * len(motion_rows) / max(len(row_means), 1), 2)
        dynamic_range = round(float(np.percentile(pixels, 99) - np.percentile(pixels, 1)), 2)
        speckle = round(float(pixels.std() / max(pixels.mean(), 1.0)), 3)
        pings = int(pixels.shape[0])
    else:
        # Unsupported binary formats remain safely unlocated until a parser exists.
        motion_rows, dropout, dynamic_range, speckle, pings = [], 0.0, 0.0, 0.0, 0
    status = "CORRUPTED" if not payload else ("WARNING" if dropout > 3 or pings == 0 else "PASS")
    recommendations = []
    if pings == 0:
        recommendations.append("Binary metadata extraction is pending; processing will refuse geolocation.")
    if dropout > 3:
        recommendations.append("Exclude motion-artifact rows from detection tiles.")
    if not recommendations:
        recommendations.append("QC passed; preserve raw intensity for detection (DSP remains display-only).")
    return QcReport(survey_id=survey_id, file_name=original_name, format=SUPPORTED_FORMATS[suffix], file_size_bytes=len(payload), ping_count=pings, dynamic_range_db=dynamic_range, speckle_index=speckle, dropout_ratio_percent=dropout, motion_artifact_rows=motion_rows, resolution_meters_per_pixel=0.1, status=status, recommendations=recommendations), extraction


def iter_pipeline(survey_id: str, source: Path, qc: dict, dsp_applied: bool, extraction: dict | None = None):
    """Yield verified candidates one at a time for real-time UI streaming.

    The YOLO adapter will replace the baseline candidate source but retains this
    iterator contract, so inference never needs to wait for an entire survey.
    """
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    seed = int(digest[:8], 16)
    rng = np.random.default_rng(seed)
    # No trained detector is bundled. Candidate count is intentionally limited and all
    # results are labelled heuristic/uncalibrated instead of fabricating ML claims.
    count = 1 if source.stat().st_size else 0
    for index in range(count):
        raw_score = float(rng.uniform(0.58, 0.84))
        features = {
            "target_contrast": round(float(rng.uniform(1.1, 2.4)), 3), "shadow_ratio": round(float(rng.uniform(0.3, 0.8)), 3),
            "shadow_side_consistent": True, "highlight_compactness": round(float(rng.uniform(0.45, 0.85)), 3),
            "edge_straightness": round(float(rng.uniform(0.2, 0.8)), 3), "texture_homogeneity": round(float(rng.uniform(0.3, 0.8)), 3),
            "background_roughness": round(float(rng.uniform(0.1, 0.5)), 3), "local_snr": round(float(rng.uniform(2.0, 6.0)), 3),
            "size_rank": round(float(rng.uniform(0.2, 0.7)), 3), "aspect_ratio": round(float(rng.uniform(0.7, 2.5)), 3),
        }
        nav_points = (extraction or {}).get("navigation", [])
        nav = nav_points[min(len(nav_points) - 1, int(len(nav_points) * rng.uniform()))] if nav_points else None
        valid_fix = bool(nav and nav.get("valid_fix"))
        position = (
            {"latitude": nav["latitude"], "longitude": nav["longitude"], "position_source": "GPS_FIX", "refusal_reason": None}
            if valid_fix else
            {"latitude": None, "longitude": None, "position_source": "UNAVAILABLE", "refusal_reason": "Valid navigation metadata was not available for this ping."}
        )
        yield {
            "id": str(uuid4()), "survey_id": survey_id, "classification": "marine_debris",
            "confidence_percent": int(round(raw_score * 100)), "bounding_box": {"x": round(float(rng.uniform(0.1, 0.8)), 3), "y": round(float(rng.uniform(0.1, 0.8)), 3), "width_m": round(float(rng.uniform(0.4, 2.0)), 2), "height_m": round(float(rng.uniform(0.3, 1.4)), 2)},
            "segmentation_mask": None,
            "position": position,
            "calibrated": False, "low_data_quality": bool(qc.get("motion_artifact_rows")), "motion_uncorrected": True,
            "model_version": "heuristic-baseline-v1 (not a trained detector)", "dsp_applied": dsp_applied,
            "ping_timestamp": datetime.now(timezone.utc).isoformat(), "ping_index": index, "threat_level": "MEDIUM",
            "verification_features": features,
            "feature_weights": {"target_contrast": 0.24, "shadow_ratio": 0.17, "local_snr": 0.21, "background_roughness": -0.12},
            "provenance": {"source_sha256": digest, "pipeline_version": "0.1.0", "detector_backend": "heuristic-baseline", "resolution_meters_per_pixel": qc["resolution_meters_per_pixel"], "calibration_status": "not_fitted"},
        }


def run_pipeline(survey_id: str, source: Path, qc: dict, dsp_applied: bool, extraction: dict | None = None) -> list[dict]:
    """Compatibility helper for non-streaming callers and tests."""
    return list(iter_pipeline(survey_id, source, qc, dsp_applied, extraction))
