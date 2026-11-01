"""Derived quantities (handoff section 4): slope angle, tilt change, movement."""

import math

import pytest

from app import derived


def test_slope_angle_level_node_is_zero():
    """R5: a level node (gravity all on z) has a slope angle of 0°."""
    assert derived.slope_angle_deg(0.0, 0.0, 1.0) == pytest.approx(0.0)


def test_slope_angle_from_known_gravity_vector():
    """R5: gravity tilted 30° about one axis gives a 30° slope angle."""
    t = math.radians(30)
    assert derived.slope_angle_deg(math.sin(t), 0.0, math.cos(t)) == pytest.approx(30.0)


def test_slope_angle_combines_both_axes():
    """R5: equal x and y components combine: atan2(sqrt(ax²+ay²), az)."""
    assert derived.slope_angle_deg(0.5, 0.5, 0.5) == pytest.approx(math.degrees(math.atan2(math.sqrt(0.5), 0.5)))


def test_tilt_change_against_baseline():
    """R5: tilt change is measured from the baseline; total = sqrt(dx² + dy²)."""
    dx, dy, total = derived.tilt_change(1.3, 0.4, 1.0, 0.0)
    assert dx == pytest.approx(0.3)
    assert dy == pytest.approx(0.4)
    assert total == pytest.approx(0.5)


def test_tilt_change_is_none_without_baseline():
    """Tilt change can't be computed until the node has a baseline."""
    assert derived.tilt_change(1.3, 0.4, None, None) == (None, None, None)


def test_haversine_known_distance():
    """Movement: 0.001° of latitude is about 111.2 m."""
    assert derived.haversine_m(-27.5, 153.0, -27.501, 153.0) == pytest.approx(111.19, abs=0.05)


def test_displacement_zero_at_reference_and_none_without_gps():
    assert derived.displacement_m(-27.5, 153.0, -27.5, 153.0) == pytest.approx(0.0)
    assert derived.displacement_m(None, 153.0, -27.5, 153.0) is None


def test_magnitudes():
    assert derived.magnitude(3.0, 4.0, 0.0) == pytest.approx(5.0)
    assert derived.magnitude(None, 1.0, 1.0) is None


def test_derive_returns_every_derived_field():
    values = {"angle_x": 6.0, "angle_y": 0.0, "acc_x": 0.0, "acc_y": 0.0, "acc_z": 1.0, "lat": -27.5, "lon": 153.0}
    out = derived.derive(values, baseline_x=5.0, baseline_y=0.0, ref_lat=-27.5, ref_lon=153.0)
    assert set(out) == set(derived.DERIVED_FIELDS)
    assert out["tilt_change_total"] == pytest.approx(1.0)
    assert out["acc_magnitude"] == pytest.approx(1.0)
    assert out["gyro_magnitude"] is None  # no gyro values given
