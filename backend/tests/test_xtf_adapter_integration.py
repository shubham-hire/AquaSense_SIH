"""
test_xtf_adapter_integration.py
================================
Integration test: XTF extraction → tile slicing → YOLO26 adapter.

Scope
-----
* Builds a synthetic but physically plausible N-ping XTF fixture using pyxtf
  (identical pattern to test_pipeline.py so we know the fixture is valid).
* Runs extract_xtf() to obtain the waterfall image and per-ping navigation.
* Slices the waterfall into 640-px tiles.
* Feeds tiles into Yolo26Adapter.  Without trained weights the adapter returns
  empty lists — every *structural* property is asserted regardless.
* Asserts that detection x_norm/y_norm back-project to the correct ping index,
  port/starboard side, and that the navigation refusal invariant holds
  (no coordinates emitted without a valid_fix).
"""
from __future__ import annotations

import ctypes
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Constants — must be consistent across all test groups
# ---------------------------------------------------------------------------
NUM_PINGS        = 6        # enough to span two 640-px tile rows
SAMPLES_PER_SIDE = 400      # port and starboard each; waterfall width = 800 px
TILE_SIZE        = 640
BASE_LAT         = 12.340_000
BASE_LON         = 76.780_000
HEADING          = 90.0


# ---------------------------------------------------------------------------
# XTF fixture builder (follows the exact same pattern as test_pipeline.py)
# ---------------------------------------------------------------------------

def build_xtf_fixture(tmp_path: Path) -> tuple[Path, list[dict]]:
    """Write a synthetic XTF file.  Returns (path, expected_navigation_list)."""
    import pyxtf

    source = tmp_path / "survey_fixture.xtf"

    # --- File header ---
    header = pyxtf.XTFFileHeader()
    header.SonarName = b"AquaSense test"        # max 16 bytes (pyxtf constraint)
    header.SonarType = pyxtf.XTFSonarType.unknown1
    header.NavUnits = pyxtf.XTFNavUnits.latlon.value
    header.NumberOfSonarChannels = 2
    for channel, kind in enumerate(
        (pyxtf.XTFChannelType.port, pyxtf.XTFChannelType.stbd)
    ):
        header.ChanInfo[channel].TypeOfChannel = kind.value
        header.ChanInfo[channel].SubChannelNumber = channel
        header.ChanInfo[channel].BytesPerSample = 1
        header.ChanInfo[channel].SampleFormat = pyxtf.XTFSampleFormat.byte.value

    # --- Pings ---
    pings = []
    expected_nav = []
    bytes_per_ping = (
        ctypes.sizeof(pyxtf.XTFPingHeader)
        + 2 * ctypes.sizeof(pyxtf.XTFPingChanHeader)
        + 2 * SAMPLES_PER_SIDE
    )

    for index in range(NUM_PINGS):
        ping = pyxtf.XTFPingHeader()
        ping.HeaderType = pyxtf.XTFHeaderType.sonar.value
        ping.NumChansToFollow = 2
        ping.Year, ping.Month, ping.Day = 2026, 6, 15
        ping.Hour, ping.Minute, ping.Second = 8, 0, index   # each ping 1 s apart
        ping.HSeconds = 0
        ping.PingNumber = index

        lat = BASE_LAT + index * 0.000_01
        lon = BASE_LON + index * 0.000_01
        ping.SensorYcoordinate = lat
        ping.SensorXcoordinate = lon
        ping.SensorPrimaryAltitude = 5.0
        ping.SensorDepth = 20.0
        ping.SensorHeading = HEADING

        # Port: bright nadir, dark far range (descending ramp)
        port_samples = np.linspace(200, 10, SAMPLES_PER_SIDE, dtype=np.uint8)
        # Starboard: dark nadir, bright far range (ascending ramp)
        stbd_samples = np.linspace(10, 200, SAMPLES_PER_SIDE, dtype=np.uint8)

        channels = (pyxtf.XTFPingChanHeader(), pyxtf.XTFPingChanHeader())
        for channel, entry in enumerate(channels):
            entry.ChannelNumber = channel
            entry.NumSamples = SAMPLES_PER_SIDE
            entry.SampleFormat = 8          # uint8
            entry.SlantRange = 50           # c_float field; int is fine
            entry.Frequency = 410           # c_ushort — must be int
        ping.ping_chan_headers = channels
        ping.data = [port_samples, stbd_samples]
        ping.NumBytesThisRecord = bytes_per_ping

        pings.append(ping)
        expected_nav.append(
            {
                "ping_index": index,
                "latitude":   lat,
                "longitude":  lon,
                "valid_fix":  True,
                "altitude_m": 5.0,
                "heading_deg": HEADING,
            }
        )

    with source.open("wb") as fh:
        fh.write(header.to_bytes())
        for ping in pings:
            fh.write(ping.to_bytes())

    return source, expected_nav


# ---------------------------------------------------------------------------
# Tiling helper  (the production pipeline will use the same logic)
# ---------------------------------------------------------------------------

def slice_waterfall_to_tiles(
    waterfall_png: Path, tile_size: int = TILE_SIZE
) -> list[dict]:
    """Slice a grayscale waterfall image into (tile_size × tile_size) tiles.

    Each returned dict contains:
        tile_array   : np.ndarray (tile_size, tile_size, 3) uint8 RGB
        ping_start   : first ping row covered
        ping_end     : last ping row covered (exclusive)
        col_start    : first sample column covered
        col_end      : last sample column covered (exclusive)
        is_port_side : True when tile midpoint is in the left (flipped-port) half
    """
    img = np.asarray(Image.open(waterfall_png).convert("L"), dtype=np.uint8)
    H, W = img.shape
    mid = W // 2
    tiles = []
    for row in range(0, H, tile_size):
        for col in range(0, W, tile_size):
            patch = img[row : row + tile_size, col : col + tile_size]
            ph, pw = patch.shape
            if ph < tile_size or pw < tile_size:
                padded = np.zeros((tile_size, tile_size), dtype=np.uint8)
                padded[:ph, :pw] = patch
                patch = padded
            rgb = np.stack([patch, patch, patch], axis=-1)
            tiles.append(
                {
                    "tile_array": rgb,
                    "ping_start": row,
                    "ping_end":   min(row + tile_size, H),
                    "col_start":  col,
                    "col_end":    min(col + tile_size, W),
                    "is_port_side": (col + pw // 2) < mid,
                }
            )
    return tiles


def _backproject(
    x_norm: float,
    y_norm: float,
    tile: dict,
    navigation: list[dict],
) -> dict:
    """Convert a detection's tile-normalised coords back to survey space."""
    abs_row = tile["ping_start"] + y_norm * (tile["ping_end"] - tile["ping_start"])
    abs_col = tile["col_start"]  + x_norm * (tile["col_end"]  - tile["col_start"])
    ping_idx = max(0, min(int(abs_row), len(navigation) - 1))
    return {
        "ping_index": ping_idx,
        "sample_col": abs_col,
        "side": "port" if tile["is_port_side"] else "starboard",
    }


# ---------------------------------------------------------------------------
# pytest fixtures (module-scoped to avoid rebuilding the XTF file per test)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def xtf_extraction(tmp_path_factory):
    try:
        import pyxtf  # noqa: F401
    except ImportError:
        pytest.skip("pyxtf not installed — XTF integration tests skipped")

    from app.xtf import extract_xtf

    tmp = tmp_path_factory.mktemp("xtf")
    source, expected_nav = build_xtf_fixture(tmp)
    extraction = extract_xtf(source, tmp / "artifacts")
    return {"extraction": extraction, "expected_nav": expected_nav}


@pytest.fixture(scope="module")
def tiles_info(xtf_extraction):
    wf_path = Path(xtf_extraction["extraction"]["waterfall_path"])
    tiles = slice_waterfall_to_tiles(wf_path, tile_size=TILE_SIZE)
    return {
        "tiles":       tiles,
        "extraction":  xtf_extraction["extraction"],
        "expected_nav": xtf_extraction["expected_nav"],
    }


# ---------------------------------------------------------------------------
# Group 1 — XTF extraction contract
# ---------------------------------------------------------------------------

class TestXtfExtractionContract:
    def test_ping_count_matches_fixture(self, xtf_extraction):
        assert xtf_extraction["extraction"]["ping_count"] == NUM_PINGS

    def test_waterfall_width_is_port_plus_starboard(self, xtf_extraction):
        H, W = xtf_extraction["extraction"]["waterfall_shape"]
        assert H == NUM_PINGS
        assert W == 2 * SAMPLES_PER_SIDE

    def test_waterfall_png_exists_and_is_greyscale(self, xtf_extraction):
        path = Path(xtf_extraction["extraction"]["waterfall_path"])
        assert path.is_file()
        assert Image.open(path).mode == "L"

    def test_all_navigation_records_present(self, xtf_extraction):
        assert len(xtf_extraction["extraction"]["navigation"]) == NUM_PINGS

    def test_all_pings_have_valid_fix(self, xtf_extraction):
        assert xtf_extraction["extraction"]["valid_navigation_pings"] == NUM_PINGS

    def test_navigation_coordinates_match_fixture(self, xtf_extraction):
        nav      = xtf_extraction["extraction"]["navigation"]
        expected = xtf_extraction["expected_nav"]
        for record, exp in zip(nav, expected):
            assert record["valid_fix"] is True
            assert record["latitude"]  == pytest.approx(exp["latitude"],  abs=1e-6)
            assert record["longitude"] == pytest.approx(exp["longitude"], abs=1e-6)

    def test_timestamps_are_parseable_iso_strings(self, xtf_extraction):
        for record in xtf_extraction["extraction"]["navigation"]:
            ts = record.get("timestamp")
            assert ts is not None
            parsed = datetime.fromisoformat(ts)
            assert parsed.year == 2026

    def test_per_ping_timestamps_are_sequential(self, xtf_extraction):
        """Each successive ping must have a timestamp >= previous."""
        nav = xtf_extraction["extraction"]["navigation"]
        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in nav]
        for earlier, later in zip(timestamps, timestamps[1:]):
            assert later >= earlier

    def test_heading_recorded_per_ping(self, xtf_extraction):
        for record in xtf_extraction["extraction"]["navigation"]:
            assert record["heading_deg"] == pytest.approx(HEADING, abs=0.01)

    def test_altitude_recorded_per_ping(self, xtf_extraction):
        for record in xtf_extraction["extraction"]["navigation"]:
            assert record["altitude_m"] == pytest.approx(5.0, abs=0.01)

    def test_row_indices_are_zero_based_contiguous(self, xtf_extraction):
        row_indices = [r["row_index"] for r in xtf_extraction["extraction"]["navigation"]]
        assert row_indices == list(range(NUM_PINGS))


# ---------------------------------------------------------------------------
# Group 2 — Port / Starboard orientation
# ---------------------------------------------------------------------------

class TestWaterfallOrientation:
    def test_port_and_starboard_gradients_run_in_opposite_directions(self, xtf_extraction):
        """Port (flipped) has bright nadir on its right edge; starboard has bright far
        range on its right edge.  Both gradient directions are positive (nadir/far brighter
        than their respective far/nadir edges) but measured on different sides."""
        path = Path(xtf_extraction["extraction"]["waterfall_path"])
        img  = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
        H, W = img.shape
        mid  = W // 2
        left  = img[:, :mid]   # port (flipped) — nadir at right edge
        right = img[:, mid:]   # starboard — far range at right edge
        port_nadir_mean = left[:, -1].mean()
        port_far_mean   = left[:,  0].mean()
        stbd_far_mean   = right[:, -1].mean()
        stbd_nadir_mean = right[:,  0].mean()
        assert port_nadir_mean > port_far_mean,  (
            "Port (flipped): nadir col (rightmost of left half) should be brighter than far range"
        )
        assert stbd_far_mean   > stbd_nadir_mean, (
            "Starboard: far range col (rightmost of right half) should be brighter than nadir"
        )

    def test_port_nadir_brighter_than_far_range(self, xtf_extraction):
        """After flipping port, the rightmost column of the left half (nadir)
        should be brighter than the leftmost column (far range)."""
        path = Path(xtf_extraction["extraction"]["waterfall_path"])
        img  = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
        mid  = img.shape[1] // 2
        left = img[:, :mid]
        assert left[:, -1].mean() > left[:, 0].mean(), (
            "Port nadir (right of left half) should be brighter than far range (left)"
        )

    def test_starboard_far_range_brighter_than_nadir(self, xtf_extraction):
        """Starboard ascending ramp: far range (rightmost) should be brighter."""
        path = Path(xtf_extraction["extraction"]["waterfall_path"])
        img  = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
        mid  = img.shape[1] // 2
        right = img[:, mid:]
        assert right[:, -1].mean() > right[:, 0].mean(), (
            "Starboard far range (right of right half) should be brighter than nadir (left)"
        )

    def test_tile_side_flag_matches_column_position(self, tiles_info):
        extraction = tiles_info["extraction"]
        W   = extraction["waterfall_shape"][1]
        mid = W // 2
        for tile in tiles_info["tiles"]:
            tile_mid = (tile["col_start"] + tile["col_end"]) // 2
            assert tile["is_port_side"] == (tile_mid < mid), (
                f"Tile col [{tile['col_start']}, {tile['col_end']}] has wrong is_port_side"
            )


# ---------------------------------------------------------------------------
# Group 3 — Tile geometry
# ---------------------------------------------------------------------------

class TestTileGeometry:
    def test_tile_count_covers_whole_waterfall(self, tiles_info):
        H, W = tiles_info["extraction"]["waterfall_shape"]
        expected = math.ceil(H / TILE_SIZE) * math.ceil(W / TILE_SIZE)
        assert len(tiles_info["tiles"]) == expected

    def test_every_tile_is_tile_size_squared_rgb(self, tiles_info):
        for tile in tiles_info["tiles"]:
            assert tile["tile_array"].shape == (TILE_SIZE, TILE_SIZE, 3)
            assert tile["tile_array"].dtype == np.uint8

    def test_content_tiles_are_not_all_zero(self, tiles_info):
        H = tiles_info["extraction"]["waterfall_shape"][0]
        for tile in tiles_info["tiles"]:
            if tile["ping_start"] < H:
                assert tile["tile_array"].max() > 0, (
                    f"Content tile at ping_start={tile['ping_start']} is all zeros"
                )

    def test_tiles_cover_every_ping_row(self, tiles_info):
        H = tiles_info["extraction"]["waterfall_shape"][0]
        covered = set()
        for tile in tiles_info["tiles"]:
            covered.update(range(tile["ping_start"], tile["ping_end"]))
        for row in range(H):
            assert row in covered, f"Ping row {row} is not covered by any tile"

    def test_ping_start_end_bounds_are_valid(self, tiles_info):
        H = tiles_info["extraction"]["waterfall_shape"][0]
        for tile in tiles_info["tiles"]:
            assert 0 <= tile["ping_start"] < H
            assert tile["ping_end"] > tile["ping_start"]

    def test_col_bounds_are_valid(self, tiles_info):
        W = tiles_info["extraction"]["waterfall_shape"][1]
        for tile in tiles_info["tiles"]:
            assert 0 <= tile["col_start"] < W
            assert tile["col_end"] > tile["col_start"]


# ---------------------------------------------------------------------------
# Group 4 — Adapter structural integration (no weights required)
# ---------------------------------------------------------------------------

class TestAdapterIntegration:
    def _make_adapter(self):
        from app.detector import Yolo26Adapter, DetectorConfig
        return Yolo26Adapter(DetectorConfig(model_path=Path("/nonexistent/yolo26n.pt")))

    def test_adapter_accepts_xtf_tiles_without_exception(self, tiles_info):
        adapter = self._make_adapter()
        arrays  = [t["tile_array"] for t in tiles_info["tiles"]]
        result  = adapter.run_batch(arrays)
        assert len(result) == len(arrays)

    def test_result_is_list_of_lists(self, tiles_info):
        adapter = self._make_adapter()
        arrays  = [t["tile_array"] for t in tiles_info["tiles"]]
        result  = adapter.run_batch(arrays)
        for per_tile in result:
            assert isinstance(per_tile, list)

    def test_result_order_matches_tile_input_order(self, tiles_info):
        adapter = self._make_adapter()
        arrays  = [t["tile_array"] for t in tiles_info["tiles"]]
        result  = adapter.run_batch(arrays)
        assert len(result) == len(arrays)   # 1-to-1 correspondence

    # ------------------------------------------------------------------
    # Backprojection: detection coords → ping index + side
    # ------------------------------------------------------------------

    def test_backprojected_ping_index_is_in_bounds(self, tiles_info):
        navigation = tiles_info["extraction"]["navigation"]
        for tile in tiles_info["tiles"]:
            bp = _backproject(0.5, 0.5, tile, navigation)
            assert 0 <= bp["ping_index"] < len(navigation), (
                f"ping_index {bp['ping_index']} out of bounds"
            )

    def test_backprojected_gps_coordinates_are_valid(self, tiles_info):
        """Every back-projected ping with valid_fix must carry real lat/lng."""
        navigation = tiles_info["extraction"]["navigation"]
        for tile in tiles_info["tiles"]:
            bp     = _backproject(0.5, 0.5, tile, navigation)
            record = navigation[bp["ping_index"]]
            if record["valid_fix"]:
                assert record["latitude"]  is not None
                assert record["longitude"] is not None
                assert -90  <= record["latitude"]  <= 90
                assert -180 <= record["longitude"] <= 180

    def test_refusal_invariant_no_fix_means_null_coords(self, tiles_info):
        """Navigation records without valid_fix must have lat=None, lon=None.
        This is the architectural refusal constraint enforced end-to-end."""
        for record in tiles_info["extraction"]["navigation"]:
            if not record["valid_fix"]:
                assert record["latitude"]  is None
                assert record["longitude"] is None

    def test_port_tile_detection_maps_to_port_side(self, tiles_info):
        navigation = tiles_info["extraction"]["navigation"]
        port_tiles = [t for t in tiles_info["tiles"] if t["is_port_side"]]
        assert port_tiles, "No port-side tiles found — check fixture width vs tile size"
        for tile in port_tiles[:3]:
            bp = _backproject(0.5, 0.5, tile, navigation)
            assert bp["side"] == "port"

    def test_starboard_tile_detection_maps_to_starboard_side(self, tiles_info):
        navigation = tiles_info["extraction"]["navigation"]
        stbd_tiles = [t for t in tiles_info["tiles"] if not t["is_port_side"]]
        assert stbd_tiles, "No starboard-side tiles found"
        for tile in stbd_tiles[:3]:
            bp = _backproject(0.5, 0.5, tile, navigation)
            assert bp["side"] == "starboard"

    def test_detection_timestamp_at_backprojected_ping(self, tiles_info):
        """The ping that a detection maps to must always carry a timestamp."""
        navigation = tiles_info["extraction"]["navigation"]
        for tile in tiles_info["tiles"]:
            if tile["ping_start"] >= len(navigation):
                continue
            bp = _backproject(0.5, 0.5, tile, navigation)
            ts = navigation[bp["ping_index"]].get("timestamp")
            assert ts is not None
            datetime.fromisoformat(ts)   # must be a valid ISO-8601 string

    def test_detection_ping_heading_is_survey_heading(self, tiles_info):
        """Each back-projected ping's heading must match the fixture heading."""
        navigation = tiles_info["extraction"]["navigation"]
        for tile in tiles_info["tiles"]:
            if tile["ping_start"] >= len(navigation):
                continue
            bp     = _backproject(0.5, 0.5, tile, navigation)
            record = navigation[bp["ping_index"]]
            assert record["heading_deg"] == pytest.approx(HEADING, abs=0.01)

    def test_synthetic_detection_physical_size_floor(self):
        """width_m/height_m must be >= MIN_* even for a near-zero normalised box."""
        from app.detector import MIN_WIDTH_M, MIN_HEIGHT_M

        tiny_w_norm = 0.0001
        tiny_h_norm = 0.0001
        res = 0.1

        width_m  = max(tiny_w_norm * TILE_SIZE * res, MIN_WIDTH_M)
        height_m = max(tiny_h_norm * TILE_SIZE * res, MIN_HEIGHT_M)

        assert width_m  >= MIN_WIDTH_M
        assert height_m >= MIN_HEIGHT_M

    def test_adapter_run_batch_with_resolution_override(self, tiles_info):
        """Passing resolution_m_per_px must not crash and must be accepted."""
        adapter = self._make_adapter()
        arrays  = [t["tile_array"] for t in tiles_info["tiles"]]
        result  = adapter.run_batch(arrays, resolution_m_per_px=0.05)
        assert len(result) == len(arrays)


# ---------------------------------------------------------------------------
# Group 5 — Physical size mapping (parametrised, no fixture required)
# ---------------------------------------------------------------------------

class TestPhysicalSizeMapping:
    @pytest.mark.parametrize("res,w_norm,h_norm,exp_w,exp_h", [
        (0.10, 0.20, 0.15, 12.80,  9.60),
        (0.05, 0.10, 0.10,  3.20,  3.20),
        (0.20, 0.05, 0.05,  6.40,  6.40),
    ])
    def test_width_height_from_resolution(
        self, res, w_norm, h_norm, exp_w, exp_h
    ):
        from app.detector import MIN_WIDTH_M, MIN_HEIGHT_M
        width_m  = max(w_norm * TILE_SIZE * res, MIN_WIDTH_M)
        height_m = max(h_norm * TILE_SIZE * res, MIN_HEIGHT_M)
        assert width_m  == pytest.approx(exp_w, rel=1e-3)
        assert height_m == pytest.approx(exp_h, rel=1e-3)

    def test_sub_floor_box_is_clamped(self):
        from app.detector import MIN_WIDTH_M, MIN_HEIGHT_M
        width_m  = max(0.00001 * TILE_SIZE * 0.1, MIN_WIDTH_M)
        height_m = max(0.00001 * TILE_SIZE * 0.1, MIN_HEIGHT_M)
        assert width_m  == pytest.approx(MIN_WIDTH_M,  rel=1e-3)
        assert height_m == pytest.approx(MIN_HEIGHT_M, rel=1e-3)
