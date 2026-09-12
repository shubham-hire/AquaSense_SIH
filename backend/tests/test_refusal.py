import pytest

from app.schemas import Position


def test_missing_navigation_is_an_explicit_refusal():
    position = Position(latitude=None, longitude=None, position_source="UNAVAILABLE", refusal_reason="No nav")
    assert position.latitude is None
    assert position.longitude is None
    assert position.position_source == "UNAVAILABLE"


def test_unavailable_navigation_cannot_leak_coordinates():
    with pytest.raises(ValueError, match="must not include coordinates"):
        Position(latitude=12.0, longitude=77.0, position_source="UNAVAILABLE", refusal_reason="No nav")
