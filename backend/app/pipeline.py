from __future__ import annotations

import hashlib
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import numpy as np
from PIL import Image

# Local development should use the same verified checkpoint committed at the
# repository root. Docker/Render can still override this with an absolute path.
os.environ.setdefault(
    "AQUASENSE_MODEL_PATH",
    str(Path(__file__).resolve().parents[2] / "best.pt"),
)

from .detector import get_adapter
from .geolocation import geolocate_detection
from .schemas import QcReport
from .taxonomy import CLASS_NAMES
from .vendor_formats import extract_jsf, extract_sl2
from .xtf import extract_xtf

SUPPORTED_FORMATS = {
    ".xtf": "XTF", ".jsf": "JSF", ".sl2": "SL2", ".tif": "GEOTIFF",
    ".tiff": "GEOTIFF", ".png": "IMAGE", ".jpg": "IMAGE", ".jpeg": "IMAGE",
}
# Backwards-compatible name for callers; the mapping itself lives in taxonomy.py.
BEST_PT_CLASS_NAMES = CLASS_NAMES
UNCALIBRATED_RESOLUTION_M_PER_PX = 0.1

# The heuristic fallback generates randomised boxes that are NOT model output.
# It must never run implicitly: an operator looking at the console cannot tell
# fabricated contacts from real ones, so processing fails loudly instead.
# Set AQUASENSE_ALLOW_SYNTHETIC_FALLBACK=1 only for offline UI demos.
SYNTHETIC_FALLBACK_ENV = "AQUASENSE_ALLOW_SYNTHETIC_FALLBACK"
SYNTHETIC_WARNING = (
    "SYNTHETIC DEMO DATA - these coordinates, sizes, and confidences were "
    "randomly generated because the detection model was unavailable. They are "
    "not sonar findings and must not be used operationally."
)
MODEL_UNAVAILABLE_MESSAGE = (
    "Detection model unavailable, so processing was refused rather than "
    "returning fabricated detections. Provide valid weights at "
    "AQUASENSE_MODEL_PATH and install ultralytics, or set "
    f"{SYNTHETIC_FALLBACK_ENV}=1 to explicitly opt in to clearly labelled "
    "synthetic demo output."
)


def synthetic_fallback_enabled() -> bool:
    """True only when an operator explicitly opted in to fabricated output."""
    return os.getenv(SYNTHETIC_FALLBACK_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_resolution(extraction: dict | None) -> float | None:
    try:
        value = float((extraction or {}).get("cross_track_resolution_m_per_pixel"))
        return value if math.isfinite(value) and value > 0 else None
    except (TypeError, ValueError):
        return None


def inspect_file(survey_id: str, source: Path, original_name: str, artifact_dir: Path | None = None) -> tuple[QcReport, dict | None]:
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported sonar format: {suffix or 'no extension'}")
    if source.stat().st_size == 0:
        return QcReport(
            survey_id=survey_id, file_name=original_name, format=SUPPORTED_FORMATS[suffix],
            file_size_bytes=0, ping_count=0, dynamic_range_db=0, speckle_index=0,
            dropout_ratio_percent=0, motion_artifact_rows=[],
            resolution_meters_per_pixel=UNCALIBRATED_RESOLUTION_M_PER_PX,
            status="CORRUPTED", recommendations=["The uploaded file is empty."],
        ), None

    extraction = None
    if suffix == ".xtf":
        if artifact_dir is None:
            raise ValueError("An artifact directory is required for XTF extraction")
        extraction = extract_xtf(source, artifact_dir)
    elif suffix == ".jsf":
        if artifact_dir is None:
            raise ValueError("An artifact directory is required for JSF extraction")
        extraction = extract_jsf(source, artifact_dir)
    elif suffix == ".sl2":
        if artifact_dir is None:
            raise ValueError("An artifact directory is required for SL2 extraction")
        extraction = extract_sl2(source, artifact_dir)

    if extraction is not None:
        motion_rows = extraction["motion_artifact_rows"]
        dropout = extraction["dropout_ratio_percent"]
        dynamic_range = extraction["dynamic_range_db"]
        speckle = extraction["speckle_index"]
        pings = extraction["ping_count"]
    else:
        with Image.open(source) as image:
            pixels = np.asarray(image.convert("L"), dtype=np.float32)
        row_means = pixels.mean(axis=1)
        local_std = max(float(row_means.std()), 1.0)
        motion_rows = np.where(np.abs(row_means - row_means.mean()) > 3 * local_std)[0].astype(int).tolist()
        dropout = round(100 * len(motion_rows) / max(len(row_means), 1), 2)
        dynamic_range = round(float(np.percentile(pixels, 99) - np.percentile(pixels, 1)), 2)
        speckle = round(float(pixels.std() / max(pixels.mean(), 1.0)), 3)
        pings = int(pixels.shape[0])

    source_resolution = _source_resolution(extraction)
    resolution = source_resolution or UNCALIBRATED_RESOLUTION_M_PER_PX
    status = "WARNING" if dropout > 3 or pings == 0 or source_resolution is None else "PASS"
    recommendations: list[str] = []
    if pings == 0:
        recommendations.append("Binary metadata extraction is pending; processing will refuse geolocation.")
    if dropout > 3:
        recommendations.append("Exclude motion-artifact rows from detection tiles.")
    if source_resolution is None:
        recommendations.append("Physical dimensions are uncalibrated because source range metadata was unavailable.")
    if not recommendations:
        recommendations.append("QC passed; physical dimensions use source-derived sonar range metadata.")

    return QcReport(
        survey_id=survey_id, file_name=original_name, format=SUPPORTED_FORMATS[suffix],
        file_size_bytes=source.stat().st_size, ping_count=pings,
        dynamic_range_db=dynamic_range, speckle_index=speckle,
        dropout_ratio_percent=dropout, motion_artifact_rows=motion_rows,
        resolution_meters_per_pixel=resolution, status=status,
        recommendations=recommendations,
    ), extraction


def _load_model_image(source: Path, extraction: dict | None) -> np.ndarray:
    image_path = Path(extraction["waterfall_path"]) if extraction else source
    with Image.open(image_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _iter_tile_batches(image: np.ndarray, tile_size: int, batch_size: int):
    height, width = image.shape[:2]
    tiles, metadata = [], []
    for top in range(0, height, tile_size):
        for left in range(0, width, tile_size):
            crop = image[top:top + tile_size, left:left + tile_size]
            tile = np.zeros((tile_size, tile_size, 3), dtype=np.uint8)
            crop_height, crop_width = crop.shape[:2]
            tile[:crop_height, :crop_width] = crop
            tiles.append(tile)
            metadata.append((left, top, crop_width, crop_height))
            if len(tiles) >= batch_size:
                yield tiles, metadata
                tiles, metadata = [], []
    if tiles:
        yield tiles, metadata


def _navigation_for_row(extraction: dict | None, row: float, image_height: int) -> dict | None:
    navigation = (extraction or {}).get("navigation", [])
    if not navigation:
        return None
    target = row / max(image_height, 1) * max(len(navigation) - 1, 0)
    return navigation[min(max(int(round(target)), 0), len(navigation) - 1)]


def _threat_level(classification: str, confidence: int) -> str:
    if classification in {"shipwreck", "submarine_pipeline"} or confidence >= 90:
        return "HIGH"
    if classification in {"ghost_net", "ghost_pot_trap", "cylinder"}:
        return "MEDIUM"
    return "LOW"


def _source_mask(mask: dict | None, left: int, top: int, image_width: int, image_height: int) -> dict | None:
    """Translate a tile-local segmentation polygon into source-image pixels."""
    if not mask or mask.get("type") != "polygon":
        return mask
    points = mask.get("data")
    if not isinstance(points, list):
        return None

    source_points = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x, y = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        source_points.append([
            round(min(max(left + x, 0), image_width), 3),
            round(min(max(top + y, 0), image_height), 3),
        ])
    return {"type": "polygon", "data": source_points} if source_points else None


def _iter_yolo_pipeline(survey_id: str, source: Path, qc: dict, dsp_applied: bool, extraction: dict | None, adapter, source_digest: str) -> Iterator[dict]:
    image = _load_model_image(source, extraction)
    image_height, image_width = image.shape[:2]
    tile_size = int(adapter.config.tile_size)
    batch_size = max(int(adapter.config.batch_size), 1)
    source_resolution = _source_resolution(extraction)
    resolution = source_resolution or float(qc["resolution_meters_per_pixel"])
    measurement_source = (
        (extraction or {}).get("measurement_source", "source_metadata")
        if source_resolution is not None else "uncalibrated_default"
    )
    measurement_status = "SOURCE_DERIVED" if source_resolution is not None else "UNCALIBRATED"
    model_path = Path(adapter.config.model_path)
    model_digest = _sha256_file(model_path) if model_path.is_file() else None

    for tiles, tile_metadata in _iter_tile_batches(image, tile_size, batch_size):
        batch_results = adapter.run_batch(tiles, resolution_m_per_px=resolution)
        for tile_result, (left, top, _crop_width, _crop_height) in zip(batch_results, tile_metadata):
            for raw in tile_result:
                # The model's boxes are normalized to each tile. Convert the
                # top-left and bottom-right corners to the original image once,
                # then expose a normalized display box alongside physical size.
                box_left = min(max(left + raw.x_norm * tile_size, 0), image_width)
                box_top = min(max(top + raw.y_norm * tile_size, 0), image_height)
                box_right = min(max(left + (raw.x_norm + raw.box_xywh_norm[2]) * tile_size, 0), image_width)
                box_bottom = min(max(top + (raw.y_norm + raw.box_xywh_norm[3]) * tile_size, 0), image_height)
                center_x = (box_left + box_right) / 2
                center_y = (box_top + box_bottom) / 2
                navigation = _navigation_for_row(extraction, center_y, image_height)
                position, location_provenance = geolocate_detection(
                    navigation=navigation, center_x_px=center_x,
                    image_width_px=image_width, extraction=extraction,
                )
                classification = BEST_PT_CLASS_NAMES.get(raw.class_id, f"unknown_{raw.class_id}")
                timestamp = (navigation.get("timestamp") if navigation else None) or datetime.now(timezone.utc).isoformat()
                ping_index = int(navigation.get("ping_index", round(center_y)) if navigation else round(center_y))
                yield {
                    "id": str(uuid4()), "survey_id": survey_id,
                    "classification": classification,
                    "confidence_percent": raw.confidence_percent,
                    "bounding_box": {
                        "x": round(min(max(center_x / max(image_width, 1), 0), 1), 6),
                        "y": round(min(max(center_y / max(image_height, 1), 0), 1), 6),
                        "width_m": round(raw.width_m, 3),
                        "height_m": round(raw.height_m, 3),
                        "image_box": {
                            "left": round(box_left / max(image_width, 1), 6),
                            "top": round(box_top / max(image_height, 1), 6),
                            "width": round(max(box_right - box_left, 0) / max(image_width, 1), 6),
                            "height": round(max(box_bottom - box_top, 0) / max(image_height, 1), 6),
                        },
                    },
                    "segmentation_mask": _source_mask(raw.seg_mask, left, top, image_width, image_height), "position": position,
                    "calibrated": False,
                    "low_data_quality": bool(qc.get("motion_artifact_rows")),
                    "motion_uncorrected": not bool(navigation and navigation.get("pitch_deg") is not None and navigation.get("roll_deg") is not None),
                    "model_version": raw.model_version, "dsp_applied": dsp_applied,
                    "ping_timestamp": timestamp, "ping_index": max(ping_index, 0),
                    "threat_level": _threat_level(classification, raw.confidence_percent),
                    "verification_features": {}, "feature_weights": {},
                    "provenance": {
                        "source_sha256": source_digest, "model_sha256": model_digest,
                        "pipeline_version": "0.4.0", "detector_backend": "ultralytics-yolo26",
                        "synthetic": False,
                        "resolution_meters_per_pixel": resolution,
                        "measurement_status": measurement_status,
                        "measurement_source": measurement_source,
                        "calibration_status": "source_metadata" if source_resolution is not None else "not_fitted",
                        "model_path": str(model_path), **location_provenance,
                    },
                }


def _iter_heuristic_fallback(survey_id: str, source: Path, qc: dict, dsp_applied: bool, extraction: dict | None, digest: str) -> Iterator[dict]:
    seed = int(digest[:8], 16)
    rng = np.random.default_rng(seed)
    if source.stat().st_size == 0:
        return
    raw_score = float(rng.uniform(0.58, 0.84))
    features = {
        "target_contrast": round(float(rng.uniform(1.1, 2.4)), 3),
        "shadow_ratio": round(float(rng.uniform(0.3, 0.8)), 3),
        "shadow_side_consistent": True,
        "highlight_compactness": round(float(rng.uniform(0.45, 0.85)), 3),
        "edge_straightness": round(float(rng.uniform(0.2, 0.8)), 3),
        "texture_homogeneity": round(float(rng.uniform(0.3, 0.8)), 3),
        "background_roughness": round(float(rng.uniform(0.1, 0.5)), 3),
        "local_snr": round(float(rng.uniform(2.0, 6.0)), 3),
        "size_rank": round(float(rng.uniform(0.2, 0.7)), 3),
        "aspect_ratio": round(float(rng.uniform(0.7, 2.5)), 3),
    }
    nav_points = (extraction or {}).get("navigation", [])
    nav = nav_points[min(len(nav_points) - 1, int(len(nav_points) * rng.uniform()))] if nav_points else None
    valid_fix = bool(nav and nav.get("valid_fix"))
    position = ({"latitude": nav["latitude"], "longitude": nav["longitude"], "position_source": "GPS_FIX", "refusal_reason": None} if valid_fix else {"latitude": None, "longitude": None, "position_source": "UNAVAILABLE", "refusal_reason": "Valid navigation metadata was not available for this ping."})
    yield {
        "id": str(uuid4()), "survey_id": survey_id, "classification": "synthetic_placeholder",
        "confidence_percent": int(round(raw_score * 100)),
        "bounding_box": {"x": round(float(rng.uniform(0.1, 0.8)), 3), "y": round(float(rng.uniform(0.1, 0.8)), 3), "width_m": round(float(rng.uniform(0.4, 2.0)), 2), "height_m": round(float(rng.uniform(0.3, 1.4)), 2)},
        "segmentation_mask": None, "position": position, "calibrated": False,
        "low_data_quality": bool(qc.get("motion_artifact_rows")), "motion_uncorrected": True,
        "model_version": "SYNTHETIC-DEMO-DATA heuristic-baseline-v1 (model unavailable)", "dsp_applied": dsp_applied,
        "ping_timestamp": datetime.now(timezone.utc).isoformat(), "ping_index": 0,
        "threat_level": "MEDIUM", "verification_features": features,
        "feature_weights": {"target_contrast": 0.24, "shadow_ratio": 0.17, "local_snr": 0.21, "background_roughness": -0.12},
        "provenance": {"source_sha256": digest, "pipeline_version": "0.4.0", "detector_backend": "heuristic-fallback", "synthetic": True, "synthetic_warning": SYNTHETIC_WARNING, "resolution_meters_per_pixel": qc["resolution_meters_per_pixel"], "measurement_status": "SIMULATED", "calibration_status": "not_fitted"},
    }


def iter_pipeline(survey_id: str, source: Path, qc: dict, dsp_applied: bool, extraction: dict | None = None):
    source_digest = _sha256_file(source)
    adapter = get_adapter()
    if adapter.is_ready:
        yield from _iter_yolo_pipeline(survey_id, source, qc, dsp_applied, extraction, adapter, source_digest)
        return
    if not synthetic_fallback_enabled():
        raise RuntimeError(MODEL_UNAVAILABLE_MESSAGE)
    yield from _iter_heuristic_fallback(survey_id, source, qc, dsp_applied, extraction, source_digest)


def run_pipeline(survey_id: str, source: Path, qc: dict, dsp_applied: bool, extraction: dict | None = None) -> list[dict]:
    return list(iter_pipeline(survey_id, source, qc, dsp_applied, extraction))
