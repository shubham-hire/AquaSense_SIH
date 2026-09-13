"""Safe JSF and SL2 sonar extraction.

Only layouts with enough public structure to preserve source evidence are decoded:
* EdgeTech JSF message type 80, uncompressed envelope/analytic traces.
* Lowrance SL2 format-2 frames with the documented 144-byte frame header.

Neither parser invents navigation. A coordinate is emitted only when its format's
validity flag is set and the converted WGS-84 pair is finite and in range.
"""
from __future__ import annotations

import json
import math
import struct
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _finite(value: Any) -> float | None:
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _valid_fix(latitude: float | None, longitude: float | None) -> bool:
    return bool(latitude is not None and longitude is not None and -90 <= latitude <= 90 and -180 <= longitude <= 180 and (latitude != 0 or longitude != 0))


def _display_image(array: np.ndarray) -> np.ndarray:
    data = np.asarray(array, dtype=np.float32)
    if data.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)
    low, high = np.percentile(data, (1, 99))
    if high <= low:
        return np.zeros_like(data, dtype=np.uint8)
    return np.clip((data - low) * 255 / (high - low), 0, 255).astype(np.uint8)


def _rows(samples: list[np.ndarray]) -> np.ndarray | None:
    if not samples:
        return None
    width = max(item.size for item in samples)
    result = np.zeros((len(samples), width), dtype=np.float32)
    for row, item in enumerate(samples):
        result[row, :item.size] = item
    return result


def _write_metadata(format_name: str, artifact_dir: Path, waterfall: np.ndarray, navigation: list[dict[str, Any]], channels: int) -> dict[str, Any]:
    display = _display_image(waterfall)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    waterfall_path = artifact_dir / "waterfall.png"
    Image.fromarray(display, mode="L").save(waterfall_path)
    row_means = display.mean(axis=1)
    std = max(float(row_means.std()), 1.0)
    motion_rows = np.where(np.abs(row_means - row_means.mean()) > 3 * std)[0].astype(int).tolist()
    metadata: dict[str, Any] = {
        "format": format_name,
        "ping_count": len(navigation),
        "sonar_channels": channels,
        "waterfall_path": str(waterfall_path),
        "waterfall_shape": [int(display.shape[0]), int(display.shape[1])],
        "dynamic_range_db": round(float(np.percentile(display, 99) - np.percentile(display, 1)), 2),
        "speckle_index": round(float(display.std() / max(display.mean(), 1.0)), 3),
        "motion_artifact_rows": motion_rows,
        "dropout_ratio_percent": round(100 * len(motion_rows) / max(len(row_means), 1), 2),
        "navigation": navigation,
        "valid_navigation_pings": sum(item["valid_fix"] for item in navigation),
    }
    metadata_path = artifact_dir / f"{format_name.lower()}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    metadata["metadata_path"] = str(metadata_path)
    return metadata


def _combine_channel_records(records: dict[int, dict[int, np.ndarray]], navigation_by_ping: dict[int, dict[str, Any]]) -> tuple[np.ndarray, list[dict[str, Any]], int]:
    """Combine port/right returns by ping without interpolating missing samples."""
    waterfall_rows: list[np.ndarray] = []
    navigation: list[dict[str, Any]] = []
    for row_index, ping_id in enumerate(sorted(records)):
        channels = records[ping_id]
        port, starboard = channels.get(0), channels.get(1)
        if port is not None and starboard is not None:
            row = np.concatenate((port[::-1], starboard))
        else:
            row = port if port is not None else starboard
        if row is None:
            continue
        nav = dict(navigation_by_ping.get(ping_id, {}))
        nav.update({"ping_index": int(ping_id), "row_index": len(navigation)})
        navigation.append(nav)
        waterfall_rows.append(np.asarray(row))
    result = _rows(waterfall_rows)
    if result is None:
        raise ValueError("Sonar file contains no supported side-scan sample records")
    channel_count = len({channel for values in records.values() for channel in values})
    return result, navigation, channel_count


def _jsf_timestamp(seconds: int, milliseconds_today: int) -> str | None:
    try:
        if seconds > 0:
            return datetime.fromtimestamp(seconds + (milliseconds_today % 1000) / 1000, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        pass
    return None


def extract_jsf(source: Path, artifact_dir: Path) -> dict[str, Any]:
    """Extract EdgeTech JSF message-type 80 port/starboard side-scan traces.

    Message type 82 is intentionally rejected: EdgeTech documents it as a legacy,
    commonly compressed layout that needs a vendor decompressor.
    """
    raw = source.read_bytes()
    if len(raw) < 16:
        raise ValueError("JSF parse failed: file is shorter than the 16-byte message header")
    position = 0
    traces: dict[int, dict[int, np.ndarray]] = defaultdict(dict)
    nav: dict[int, dict[str, Any]] = {}
    unsupported_compressed = 0
    while position + 16 <= len(raw):
        marker, _protocol, _session, message_type, _command, subsystem, channel, _sequence, _reserved, byte_count = struct.unpack_from("<HBBHBBBBHI", raw, position)
        if marker != 0x1601:
            raise ValueError(f"JSF parse failed: invalid message marker at byte {position}")
        payload_start, payload_end = position + 16, position + 16 + byte_count
        if payload_end > len(raw):
            raise ValueError("JSF parse failed: truncated message payload")
        payload = raw[payload_start:payload_end]
        position = payload_end
        if message_type != 80 or subsystem not in (20, 21) or channel not in (0, 1):
            if message_type == 82:
                unsupported_compressed += 1
            continue
        if len(payload) < 240:
            raise ValueError("JSF parse failed: message type 80 header is shorter than 240 bytes")
        data_format = struct.unpack_from("<h", payload, 34)[0]
        sample_count = struct.unpack_from("<H", payload, 114)[0]
        if data_format not in (0, 1):
            unsupported_compressed += 1
            continue
        words_per_sample = 1 if data_format == 0 else 2
        required = 240 + sample_count * words_per_sample * 2
        if sample_count == 0 or len(payload) < required:
            raise ValueError("JSF parse failed: invalid sample count or truncated sonar trace")
        samples = np.frombuffer(payload, dtype="<u2", count=sample_count * words_per_sample, offset=240).astype(np.float32)
        if data_format == 1:
            samples = np.hypot(samples[0::2], samples[1::2])
        ping_id = struct.unpack_from("<I", payload, 8)[0]
        # Keep one port/starboard pair for every ping; repeated packets replace only
        # their own channel, never another channel's return.
        traces[ping_id][channel] = samples
        flags = struct.unpack_from("<H", payload, 30)[0]
        coordinate_units = struct.unpack_from("<h", payload, 88)[0]
        longitude = latitude = None
        if flags & 0x0001 and coordinate_units == 2:
            longitude = _finite(struct.unpack_from("<i", payload, 80)[0] / 600_000)
            latitude = _finite(struct.unpack_from("<i", payload, 84)[0] / 600_000)
        valid_fix = _valid_fix(latitude, longitude)
        heading = struct.unpack_from("<H", payload, 172)[0] / 100 if flags & 0x0008 else None
        pitch = struct.unpack_from("<h", payload, 174)[0] * 180 / 32768 if flags & 0x0020 else None
        roll = struct.unpack_from("<h", payload, 176)[0] * 180 / 32768 if flags & 0x0020 else None
        altitude_raw = struct.unpack_from("<i", payload, 144)[0]
        depth_raw = struct.unpack_from("<i", payload, 136)[0]
        nav[ping_id] = {
            "timestamp": _jsf_timestamp(struct.unpack_from("<i", payload, 0)[0], struct.unpack_from("<I", payload, 200)[0]),
            "latitude": latitude if valid_fix else None,
            "longitude": longitude if valid_fix else None,
            "valid_fix": valid_fix,
            "altitude_m": altitude_raw / 1000 if flags & 0x0040 and altitude_raw > 0 else None,
            "depth_m": depth_raw / 1000 if flags & 0x0200 and depth_raw > 0 else None,
            "heading_deg": heading,
            "pitch_deg": pitch,
            "roll_deg": roll,
            "heave_m": None,
            "speed_mps": None,
        }
    if not traces:
        detail = "JSF only contains legacy/compressed or unsupported sonar messages" if unsupported_compressed else "JSF contains no side-scan message type 80 records"
        raise ValueError(detail)
    waterfall, navigation, channels = _combine_channel_records(traces, nav)
    return _write_metadata("JSF", artifact_dir, waterfall, navigation, channels)


_EARTH_RADIUS_M = 6_356_752.3142


def _sl2_coordinate(easting: int, northing: int) -> tuple[float | None, float | None]:
    """Lowrance format-2 coordinates are polar-Mercator metre-like integers."""
    try:
        longitude = easting / _EARTH_RADIUS_M * 180 / math.pi
        latitude = (2 * math.atan(math.exp(northing / _EARTH_RADIUS_M)) - math.pi / 2) * 180 / math.pi
    except (OverflowError, ValueError):
        return None, None
    return _finite(latitude), _finite(longitude)


def extract_sl2(source: Path, artifact_dir: Path) -> dict[str, Any]:
    """Extract Lowrance/Simrad SL2 format-2 side-scan frames.

    SL2 is closed and varies by firmware. This supports the documented v2 header
    and rejects malformed frame boundaries instead of scanning arbitrary bytes.
    """
    raw = source.read_bytes()
    if len(raw) < 8:
        raise ValueError("SL2 parse failed: file is shorter than the 8-byte header")
    format_id, _version, _block_hint, _reserved = struct.unpack_from("<HHHH", raw, 0)
    if format_id != 2:
        raise ValueError(f"SL2 parse failed: expected Lowrance format 2, found format {format_id}")
    position = 8
    traces: dict[int, dict[int, np.ndarray]] = defaultdict(dict)
    nav: dict[int, dict[str, Any]] = {}
    while position + 144 <= len(raw):
        declared_offset = struct.unpack_from("<I", raw, position)[0]
        block_size, channel, packet_size, frame_index = struct.unpack_from("<HHHI", raw, position + 28)
        if declared_offset not in (0, position):
            raise ValueError(f"SL2 parse failed: frame offset mismatch at byte {position}")
        if block_size < 144 or position + block_size > len(raw):
            raise ValueError(f"SL2 parse failed: invalid frame size at byte {position}")
        if packet_size > block_size - 144:
            raise ValueError(f"SL2 parse failed: packet exceeds frame at byte {position}")
        if channel in (3, 4):  # left/port and right/starboard sidescan
            raw_samples = np.frombuffer(raw, dtype=np.uint8, count=packet_size, offset=position + 144).astype(np.float32)
            traces[frame_index][0 if channel == 3 else 1] = raw_samples
            flags = struct.unpack_from("<H", raw, position + 132)[0]
            longitude_raw, latitude_raw = struct.unpack_from("<ii", raw, position + 108)
            latitude = longitude = None
            if flags & 0x0010:
                latitude, longitude = _sl2_coordinate(longitude_raw, latitude_raw)
            valid_fix = _valid_fix(latitude, longitude)
            altitude_ft = struct.unpack_from("<f", raw, position + 124)[0]
            depth_ft = struct.unpack_from("<f", raw, position + 64)[0]
            heading_rad = struct.unpack_from("<f", raw, position + 128)[0]
            speed_knots = struct.unpack_from("<f", raw, position + 100)[0]
            nav[frame_index] = {
                "timestamp": None,  # SL2 v2 time1 epoch/resolution is vendor-specific.
                "latitude": latitude if valid_fix else None,
                "longitude": longitude if valid_fix else None,
                "valid_fix": valid_fix,
                "altitude_m": altitude_ft * 0.3048 if flags & 0x0200 and _finite(altitude_ft) not in (None, 0.0) else None,
                "depth_m": depth_ft * 0.3048 if _finite(depth_ft) not in (None, 0.0) else None,
                "heading_deg": math.degrees(heading_rad) % 360 if flags & 0x0100 and _finite(heading_rad) is not None else None,
                "pitch_deg": None,
                "roll_deg": None,
                "heave_m": None,
                "speed_mps": speed_knots * 0.514444 if flags & 0x0002 and _finite(speed_knots) is not None else None,
            }
        position += block_size
    if not traces:
        raise ValueError("SL2 contains no documented left/right side-scan frames")
    waterfall, navigation, channels = _combine_channel_records(traces, nav)
    return _write_metadata("SL2", artifact_dir, waterfall, navigation, channels)
