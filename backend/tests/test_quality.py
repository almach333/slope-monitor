"""R8 (proposed): detect and flag invalid or missing data."""

from app import quality


def test_values_in_range_are_not_flagged():
    """R8: normal values get no flags."""
    assert quality.check_ranges({"angle_x": 5, "acc_z": 1.0, "humidity": 60, "battery_pct": 80}) == []


def test_out_of_range_values_are_flagged():
    """R8: angle ±90°, acceleration ±16 g, humidity 0-100 % etc. are enforced."""
    flags = quality.check_ranges({"angle_x": 99.0, "acc_z": 20.0, "humidity": 101.0, "temperature": -50.0, "lat": 95.0})
    assert set(flags) == {
        "angle_x_out_of_range",
        "acc_z_out_of_range",
        "humidity_out_of_range",
        "temperature_out_of_range",
        "lat_out_of_range",
    }


def test_missing_values_are_not_flagged():
    """Missing optional fields are allowed (not an error)."""
    assert quality.check_ranges({"angle_x": None}) == []


def test_tilt_jump_over_10_degrees_is_a_spike():
    """R8: a tilt jump of more than 10° from the previous valid reading is flagged."""
    assert quality.is_spike(16.0, 0.0, 5.0, 0.0)
    assert not quality.is_spike(14.0, 0.0, 5.0, 0.0)
    assert not quality.is_spike(16.0, 0.0, None, None)  # nothing to compare with


def test_flags_invalidate_dependent_derived_fields():
    """R8: a bad angle invalidates tilt change, but not unrelated fields."""
    bad = quality.invalid_fields(["angle_x_out_of_range"])
    assert {"angle_x", "tilt_change_x", "tilt_change_total"} <= bad
    assert "slope_angle" not in bad
    assert "battery_pct" not in bad


def test_bad_humidity_does_not_affect_tilt():
    """R8/R5: a broken humidity sensor must not stop tilt alerts."""
    assert quality.is_valid_for("tilt_change_total", ["humidity_out_of_range"])
    assert not quality.is_valid_for("humidity", ["humidity_out_of_range"])


def test_spike_flag_invalidates_tilt_and_bad_acc_invalidates_slope_angle():
    assert not quality.is_valid_for("tilt_change_total", [quality.SPIKE_FLAG])
    assert not quality.is_valid_for("slope_angle", ["acc_z_out_of_range"])
    assert not quality.is_valid_for("acc_magnitude", ["acc_z_out_of_range"])
