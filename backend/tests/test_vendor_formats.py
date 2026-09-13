from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np
import pytest

from app.pipeline import inspect_file
from app.vendor_formats import _EARTH_RADIUS_M, extract_jsf, extract_sl2


def _jsf_message(ping: int, channel: int, samples: list[int], *, valid_nav: bool) -> bytes:
    payload = bytearray(240 + 2 * len(samples))
    flags = 0x0001 | 0x0008 | 0x0020 | 0x0040 | 0x0200 if valid_nav else 0
    struct.pack_into("<iI", payload, 0, 1_700_000_000, 0)  # epoch and start depth
    struct.pack_into("<I", payload, 8, ping)
    struct.pack_into("<Hh", payload, 30, flags, 0)          # validity, reserved
    struct.pack_into("<h", payload, 34, 0)                  # envelope samples
    struct.pack_into("<iiH", payload, 80, int(76.78 * 600_000), int(12.34 * 600_000), 2)
    struct.pack_into("<H", payload, 114, len(samples))
    struct.pack_into("<ii", payload, 136, 25_000, 6_000)    # depth/altitude mm
    struct.pack_into("<Hhh", payload, 172, 9_000, 1_000, -1_000)
    struct.pack_into("<I", payload, 200, 12_345)
    struct.pack_into(f"<{len(samples)}H", payload, 240, *samples)
    header = struct.pack("<HBBHBBBBHI", 0x1601, 8, 0, 80, 2, 21, channel, 0, 0, len(payload))
    return header + payload


def _write_jsf(path: Path) -> None:
    path.write_bytes(
        _jsf_message(10, 0, [10, 20, 30], valid_nav=True)
        + _jsf_message(10, 1, [40, 50, 60], valid_nav=True)
        + _jsf_message(11, 0, [15, 25, 35], valid_nav=False)
        + _jsf_message(11, 1, [45, 55, 65], valid_nav=False)
    )


def _sl2_coordinate_values(latitude: float, longitude: float) -> tuple[int, int]:
    easting = round(longitude * math.pi / 180 * _EARTH_RADIUS_M)
    northing = round(_EARTH_RADIUS_M * math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2)))
    return easting, northing


def _sl2_frame(offset: int, frame_index: int, channel: int, samples: bytes, *, valid_nav: bool) -> bytes:
    size = 144 + len(samples)
    header = bytearray(144)
    struct.pack_into("<I", header, 0, offset)
    struct.pack_into("<HHHI", header, 28, size, channel, len(samples), frame_index)
    struct.pack_into("<f", header, 64, 40.0)    # depth feet
    struct.pack_into("<f", header, 100, 4.0)    # GPS knots
    east, north = _sl2_coordinate_values(12.34, 76.78)
    struct.pack_into("<ii", header, 108, east, north)
    struct.pack_into("<ffH", header, 124, 15.0, math.radians(90), 0x0010 | 0x0200 | 0x0100 | 0x0002 if valid_nav else 0)
    return bytes(header) + samples


def _write_sl2(path: Path) -> None:
    data = bytearray(struct.pack("<HHHH", 2, 1, 0, 0))
    data.extend(_sl2_frame(len(data), 4, 3, bytes([1, 2, 3]), valid_nav=True))
    data.extend(_sl2_frame(len(data), 4, 4, bytes([4, 5, 6]), valid_nav=True))
    data.extend(_sl2_frame(len(data), 5, 3, bytes([7, 8, 9]), valid_nav=False))
    data.extend(_sl2_frame(len(data), 5, 4, bytes([10, 11, 12]), valid_nav=False))
    path.write_bytes(data)


def test_extract_jsf_builds_waterfall_and_refuses_missing_navigation(tmp_path: Path):
    source = tmp_path / "survey.jsf"
    _write_jsf(source)
    metadata = extract_jsf(source, tmp_path / "artifacts")
    assert metadata["format"] == "JSF"
    assert metadata["ping_count"] == 2
    assert metadata["waterfall_shape"] == [2, 6]
    assert metadata["valid_navigation_pings"] == 1
    assert metadata["navigation"][0]["latitude"] == pytest.approx(12.34)
    assert metadata["navigation"][0]["longitude"] == pytest.approx(76.78)
    assert metadata["navigation"][1]["valid_fix"] is False
    assert metadata["navigation"][1]["latitude"] is None
    assert Path(metadata["waterfall_path"]).is_file()


def test_extract_sl2_builds_waterfall_and_refuses_missing_navigation(tmp_path: Path):
    source = tmp_path / "survey.sl2"
    _write_sl2(source)
    metadata = extract_sl2(source, tmp_path / "artifacts")
    assert metadata["format"] == "SL2"
    assert metadata["ping_count"] == 2
    assert metadata["waterfall_shape"] == [2, 6]
    assert metadata["valid_navigation_pings"] == 1
    assert metadata["navigation"][0]["latitude"] == pytest.approx(12.34, abs=1e-5)
    assert metadata["navigation"][0]["longitude"] == pytest.approx(76.78, abs=1e-5)
    assert metadata["navigation"][1]["valid_fix"] is False
    assert metadata["navigation"][1]["longitude"] is None
    assert Path(metadata["waterfall_path"]).is_file()


@pytest.mark.parametrize("suffix, writer", [(".jsf", _write_jsf), (".sl2", _write_sl2)])
def test_inspection_uses_vendor_extraction(tmp_path: Path, suffix: str, writer):
    source = tmp_path / f"survey{suffix}"
    writer(source)
    qc, extraction = inspect_file("survey-vendor", source, source.name, tmp_path / "artifacts")
    assert extraction is not None
    assert qc.ping_count == 2
    assert qc.status == "PASS"


def test_vendor_parsers_refuse_malformed_records(tmp_path: Path):
    bad_jsf = tmp_path / "bad.jsf"
    bad_jsf.write_bytes(b"not-a-jsf")
    with pytest.raises(ValueError, match="JSF parse failed"):
        extract_jsf(bad_jsf, tmp_path / "jsf")

    bad_sl2 = tmp_path / "bad.sl2"
    bad_sl2.write_bytes(struct.pack("<HHHH", 2, 1, 0, 0) + b"short")
    with pytest.raises(ValueError, match="no documented"):
        extract_sl2(bad_sl2, tmp_path / "sl2")
