"""Native Triton XTF extraction using pyxtf.

Raw data, waterfall imagery, navigation, and measurement metadata remain
separate. Values are emitted only when observed in source headers.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _timestamp(ping: Any) -> str | None:
    try:
        return datetime(
            int(ping.Year), int(ping.Month), int(ping.Day), int(ping.Hour),
            int(ping.Minute), int(ping.Second), int(ping.HSeconds) * 10_000,
            tzinfo=timezone.utc,
        ).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _finite(value: Any) -> float | None:
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _ping_cross_track_resolution(ping: Any) -> float | None:
    """Calculate metres per sample from observed XTF channel headers."""
    resolutions: list[float] = []
    headers = getattr(ping, "ping_chan_headers", None) or []
    data_channels = getattr(ping, "data", None) or []
    for index, channel_header in enumerate(headers):
        slant_range = _finite(getattr(channel_header, "SlantRange", None))
        sample_count = _finite(getattr(channel_header, "NumSamples", None))
        if (sample_count is None or sample_count <= 0) and index < len(data_channels):
            sample_count = float(np.asarray(data_channels[index]).size)
        if slant_range is not None and slant_range > 0 and sample_count is not None and sample_count > 0:
            resolutions.append(slant_range / sample_count)
    if not resolutions:
        return None
    return float(np.median(np.asarray(resolutions, dtype=np.float64)))


def _navigation_record(ping: Any, index: int) -> dict[str, Any]:
    latitude = _finite(getattr(ping, "SensorYcoordinate", None))
    longitude = _finite(getattr(ping, "SensorXcoordinate", None))
    valid_fix = (
        latitude is not None and longitude is not None and -90 <= latitude <= 90
        and -180 <= longitude <= 180 and (latitude != 0 or longitude != 0)
    )
    return {
        "ping_index": int(getattr(ping, "PingNumber", index)),
        "row_index": index,
        "timestamp": _timestamp(ping),
        "latitude": latitude if valid_fix else None,
        "longitude": longitude if valid_fix else None,
        "valid_fix": valid_fix,
        "altitude_m": _finite(getattr(ping, "SensorPrimaryAltitude", None)),
        "depth_m": _finite(getattr(ping, "SensorDepth", None)),
        "heading_deg": _finite(getattr(ping, "SensorHeading", None)),
        "pitch_deg": _finite(getattr(ping, "SensorPitch", None)),
        "roll_deg": _finite(getattr(ping, "SensorRoll", None)),
        "heave_m": _finite(getattr(ping, "Heave", None)),
        "speed_mps": _finite(getattr(ping, "SensorSpeed", None)),
        "cross_track_resolution_m_per_pixel": _ping_cross_track_resolution(ping),
    }


def _to_display_image(array: np.ndarray) -> np.ndarray:
    data = np.asarray(array, dtype=np.float32)
    if data.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)
    low, high = np.percentile(data, (1, 99))
    if high <= low:
        return np.zeros_like(data, dtype=np.uint8)
    return np.clip((data - low) * 255 / (high - low), 0, 255).astype(np.uint8)


def _channel_image(pyxtf: Any, header: Any, pings: list[Any], channel: int) -> np.ndarray | None:
    if not pings or not any(len(getattr(ping, "data", [])) > channel for ping in pings):
        return None
    try:
        return np.asarray(pyxtf.concatenate_channel(pings.copy(), file_header=header, channel=channel, weighted=False))
    except (IndexError, RuntimeError, ValueError):
        samples = [np.asarray(ping.data[channel]).ravel() for ping in pings if len(getattr(ping, "data", [])) > channel]
        if not samples:
            return None
        width = max(sample.size for sample in samples)
        result = np.zeros((len(samples), width), dtype=samples[0].dtype)
        for row, sample in enumerate(samples):
            result[row, :sample.size] = sample
        return result


def extract_xtf(source: Path, artifact_dir: Path) -> dict[str, Any]:
    """Extract side-scan channels, waterfall PNG, nav, and XTF resolution."""
    try:
        import pyxtf
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyxtf is required to ingest .xtf files") from exc

    try:
        header, packets = pyxtf.xtf_read(str(source))
    except Exception as exc:
        raise ValueError(f"XTF parse failed: {exc}") from exc
    pings = packets.get(pyxtf.XTFHeaderType.sonar, [])
    if not pings:
        raise ValueError("XTF contains no side-scan sonar ping packets")

    port = _channel_image(pyxtf, header, pings, 0)
    starboard = _channel_image(pyxtf, header, pings, 1)
    if port is not None and starboard is not None:
        waterfall = np.hstack((np.fliplr(port), starboard))
    else:
        waterfall = port if port is not None else starboard
    if waterfall is None:
        raise ValueError("XTF sonar packets contain no channel samples")

    display = _to_display_image(waterfall)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    waterfall_path = artifact_dir / "waterfall.png"
    Image.fromarray(display, mode="L").save(waterfall_path)
    navigation = [_navigation_record(ping, index) for index, ping in enumerate(pings)]
    observed_resolutions = [
        item["cross_track_resolution_m_per_pixel"]
        for item in navigation
        if item["cross_track_resolution_m_per_pixel"] is not None
    ]
    source_resolution = (
        float(np.median(np.asarray(observed_resolutions, dtype=np.float64)))
        if observed_resolutions else None
    )
    row_means = display.mean(axis=1)
    std = max(float(row_means.std()), 1.0)
    motion_rows = np.where(np.abs(row_means - row_means.mean()) > 3 * std)[0].astype(int).tolist()
    metadata = {
        "format": "XTF",
        "ping_count": len(pings),
        "sonar_channels": int(getattr(header, "NumberOfSonarChannels", 0)),
        "waterfall_path": str(waterfall_path),
        "waterfall_shape": [int(display.shape[0]), int(display.shape[1])],
        "cross_track_resolution_m_per_pixel": source_resolution,
        "measurement_source": "xtf_channel_slant_range" if source_resolution is not None else "unavailable",
        "dynamic_range_db": round(float(np.percentile(display, 99) - np.percentile(display, 1)), 2),
        "speckle_index": round(float(display.std() / max(display.mean(), 1.0)), 3),
        "motion_artifact_rows": motion_rows,
        "dropout_ratio_percent": round(100 * len(motion_rows) / max(len(row_means), 1), 2),
        "navigation": navigation,
        "valid_navigation_pings": sum(item["valid_fix"] for item in navigation),
    }
    metadata_path = artifact_dir / "xtf_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    metadata["metadata_path"] = str(metadata_path)
    return metadata
