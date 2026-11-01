"""Data-quality checks (handoff.md section 10, requirement R8).

Bad values are FLAGGED, never dropped. Flags are per field (e.g.
"temperature_out_of_range"), so a broken humidity sensor doesn't stop tilt
alerts from working. The same flag -> field mapping is used for alert
evaluation, baseline calculation and hiding points on charts.
"""

from collections.abc import Iterable, Mapping

from app.derived import DERIVED_DEPENDS_ON

# Valid (min, max) range for each raw field. Values outside are flagged.
RANGES: dict[str, tuple[float, float]] = {
    "angle_x": (-90.0, 90.0),
    "angle_y": (-90.0, 90.0),
    "angle_z": (-360.0, 360.0),  # heading, so a wider range than the tilt axes
    "acc_x": (-16.0, 16.0),
    "acc_y": (-16.0, 16.0),
    "acc_z": (-16.0, 16.0),
    "gyro_x": (-2000.0, 2000.0),
    "gyro_y": (-2000.0, 2000.0),
    "gyro_z": (-2000.0, 2000.0),
    "temperature": (-40.0, 85.0),
    "humidity": (0.0, 100.0),
    "battery_pct": (0.0, 100.0),
    "lat": (-90.0, 90.0),
    "lon": (-180.0, 180.0),
}

# A tilt jump bigger than this (degrees) from the previous valid reading is
# flagged as a spike. Limitation: a genuine sudden failure larger than this
# would also be flagged; it is still stored and visible with "show flagged".
SPIKE_THRESHOLD_DEG = 10.0

SPIKE_FLAG = "tilt_spike"
OUT_OF_RANGE_SUFFIX = "_out_of_range"


def check_ranges(values: Mapping[str, float | None]) -> list[str]:
    """Return a flag for every raw value outside its valid range."""
    flags = []
    for field, (low, high) in RANGES.items():
        v = values.get(field)
        if v is not None and not (low <= v <= high):
            flags.append(f"{field}{OUT_OF_RANGE_SUFFIX}")
    return flags


def is_spike(
    angle_x: float | None,
    angle_y: float | None,
    prev_angle_x: float | None,
    prev_angle_y: float | None,
) -> bool:
    """True if tilt jumped more than SPIKE_THRESHOLD_DEG since the previous valid reading."""
    if None in (angle_x, angle_y, prev_angle_x, prev_angle_y):
        return False
    return (
        abs(angle_x - prev_angle_x) > SPIKE_THRESHOLD_DEG
        or abs(angle_y - prev_angle_y) > SPIKE_THRESHOLD_DEG
    )


def _raw_fields_for_flag(flag: str) -> set[str]:
    if flag == SPIKE_FLAG:
        return {"angle_x", "angle_y"}
    if flag.endswith(OUT_OF_RANGE_SUFFIX):
        return {flag[: -len(OUT_OF_RANGE_SUFFIX)]}
    return set()


def invalid_fields(flags: Iterable[str]) -> set[str]:
    """All raw AND derived fields made invalid by a reading's flags."""
    bad_raw: set[str] = set()
    for flag in flags or []:
        bad_raw |= _raw_fields_for_flag(flag)
    bad = set(bad_raw)
    for derived_field, depends_on in DERIVED_DEPENDS_ON.items():
        if bad_raw.intersection(depends_on):
            bad.add(derived_field)
    return bad


def is_valid_for(field: str, flags: Iterable[str]) -> bool:
    """True if this field of a reading can be trusted (not affected by any flag)."""
    return field not in invalid_fields(flags)
