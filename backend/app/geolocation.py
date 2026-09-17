"""Conservative target geolocation for side-scan sonar detections."""
from __future__ import annotations

import math
from typing import Any

EARTH_RADIUS_M = 6_371_008.8


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _unavailable(reason: str) -> tuple[dict, dict]:
    return (
        {
            "latitude": None,
            "longitude": None,
            "position_source": "UNAVAILABLE",
            "refusal_reason": reason,
        },
        {
            "position_method": "refused",
            "cross_track_m": None,
            "side": None,
        },
    )


def destination_point(
    latitude: float,
    longitude: float,
    bearing_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    """Project a WGS-84-like point over a short distance on a sphere."""
    angular_distance = distance_m / EARTH_RADIUS_M
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    projected_latitude = math.degrees(lat2)
    projected_longitude = (math.degrees(lon2) + 540) % 360 - 180
    return projected_latitude, projected_longitude


def geolocate_detection(
    navigation: dict | None,
    center_x_px: float,
    image_width_px: int,
    extraction: dict | None,
) -> tuple[dict, dict]:
    """Return projected target coordinates only when all source inputs exist.

    Waterfall convention is port on the left and starboard on the right. The
    function refuses to substitute the sonar/vessel fix for the target when
    heading or cross-track scale is unavailable.
    """
    if not navigation or not navigation.get("valid_fix"):
        return _unavailable("Valid source navigation was unavailable for this detection row.")

    latitude = _finite(navigation.get("latitude"))
    longitude = _finite(navigation.get("longitude"))
    if latitude is None or longitude is None or not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return _unavailable("Source navigation coordinates were invalid.")

    heading = _finite(navigation.get("heading_deg"))
    if heading is None:
        return _unavailable("Target geolocation requires source heading metadata.")

    metadata = extraction or {}
    resolution = _finite(
        navigation.get("cross_track_resolution_m_per_pixel")
        or metadata.get("cross_track_resolution_m_per_pixel")
    )
    if resolution is None or resolution <= 0:
        return _unavailable(
            "Target geolocation requires source-derived cross-track resolution."
        )

    if image_width_px <= 0:
        return _unavailable("Target geolocation requires a valid waterfall width.")

    offset_pixels = center_x_px - image_width_px / 2
    cross_track_m = offset_pixels * resolution
    side = "starboard" if cross_track_m > 0 else "port" if cross_track_m < 0 else "nadir"
    bearing = heading if side == "nadir" else heading + (90 if side == "starboard" else -90)
    target_latitude, target_longitude = destination_point(
        latitude, longitude, bearing, abs(cross_track_m)
    )

    return (
        {
            "latitude": round(target_latitude, 8),
            "longitude": round(target_longitude, 8),
            "position_source": "GPS_FIX",
            "refusal_reason": None,
        },
        {
            "position_method": "heading_cross_track_projection",
            "cross_track_m": round(cross_track_m, 3),
            "side": side,
            "source_latitude": latitude,
            "source_longitude": longitude,
            "source_heading_deg": heading % 360,
            "cross_track_resolution_m_per_pixel": resolution,
        },
    )
