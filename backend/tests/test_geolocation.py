import math

from app.geolocation import destination_point, geolocate_detection


def _nav(**updates):
    value = {
        "valid_fix": True,
        "latitude": 12.0,
        "longitude": 77.0,
        "heading_deg": 0.0,
    }
    value.update(updates)
    return value


def test_starboard_target_projects_east_for_northbound_sonar():
    position, metadata = geolocate_detection(
        _nav(), center_x_px=600, image_width_px=1000,
        extraction={"cross_track_resolution_m_per_pixel": 0.5},
    )
    assert position["position_source"] == "GPS_FIX"
    assert position["longitude"] > 77.0
    assert abs(position["latitude"] - 12.0) < 0.00001
    assert metadata["side"] == "starboard"
    assert metadata["cross_track_m"] == 50.0


def test_port_target_projects_west_for_northbound_sonar():
    position, metadata = geolocate_detection(
        _nav(), center_x_px=400, image_width_px=1000,
        extraction={"cross_track_resolution_m_per_pixel": 0.5},
    )
    assert position["longitude"] < 77.0
    assert metadata["side"] == "port"
    assert metadata["cross_track_m"] == -50.0


def test_missing_heading_refuses_vessel_position_substitution():
    position, metadata = geolocate_detection(
        _nav(heading_deg=None), center_x_px=600, image_width_px=1000,
        extraction={"cross_track_resolution_m_per_pixel": 0.5},
    )
    assert position["position_source"] == "UNAVAILABLE"
    assert position["latitude"] is None
    assert "heading" in position["refusal_reason"]
    assert metadata["position_method"] == "refused"


def test_missing_cross_track_resolution_refuses_location():
    position, _ = geolocate_detection(
        _nav(), center_x_px=600, image_width_px=1000, extraction={}
    )
    assert position["position_source"] == "UNAVAILABLE"
    assert "cross-track resolution" in position["refusal_reason"]


def test_invalid_navigation_is_refused():
    position, _ = geolocate_detection(
        _nav(latitude=120), center_x_px=500, image_width_px=1000,
        extraction={"cross_track_resolution_m_per_pixel": 0.5},
    )
    assert position["position_source"] == "UNAVAILABLE"


def test_destination_point_preserves_origin_at_zero_distance():
    latitude, longitude = destination_point(12.34, 76.78, 123, 0)
    assert math.isclose(latitude, 12.34)
    assert math.isclose(longitude, 76.78)
