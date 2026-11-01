"""Derived quantities computed from raw sensor values (handoff.md section 4).

Everything here is plain maths with no database access, so it is easy to
test and easy to change if the definitions of "tilt", "slope angle" or
"movement" are revised with the supervisor.

Nothing derived is stored in the database. These functions run every time
readings are read, so changing a node's baseline or reference position
immediately updates all historical values too.
"""

import math
from collections.abc import Mapping

# Raw fields a reading can carry (all optional except the timestamp).
RAW_FIELDS = [
    "lat", "lon",
    "angle_x", "angle_y", "angle_z",
    "acc_x", "acc_y", "acc_z",
    "gyro_x", "gyro_y", "gyro_z",
    "mag_x", "mag_y", "mag_z",
    "temperature", "humidity",
    "battery_pct", "battery_v",
    "rssi", "snr",
]

# Fields computed by derive(), and the raw fields each one depends on.
# quality.py uses this map: if a raw field is flagged as bad, every derived
# field that depends on it is treated as bad too.
DERIVED_DEPENDS_ON: dict[str, list[str]] = {
    "tilt_change_x": ["angle_x"],
    "tilt_change_y": ["angle_y"],
    "tilt_change_total": ["angle_x", "angle_y"],
    "slope_angle": ["acc_x", "acc_y", "acc_z"],
    "acc_magnitude": ["acc_x", "acc_y", "acc_z"],
    "gyro_magnitude": ["gyro_x", "gyro_y", "gyro_z"],
    "mag_magnitude": ["mag_x", "mag_y", "mag_z"],
    "displacement_m": ["lat", "lon"],
}
DERIVED_FIELDS = list(DERIVED_DEPENDS_ON)

ALL_FIELDS = RAW_FIELDS + DERIVED_FIELDS

EARTH_RADIUS_M = 6_371_000.0


def magnitude(x: float | None, y: float | None, z: float | None) -> float | None:
    """Length of a 3-axis vector, e.g. total acceleration in g."""
    if x is None or y is None or z is None:
        return None
    return math.sqrt(x * x + y * y + z * z)


def slope_angle_deg(ax: float | None, ay: float | None, az: float | None) -> float | None:
    """Overall inclination from horizontal, from the accelerometer's gravity vector.

    When the node is perfectly level, gravity is all on the z axis and the
    angle is 0 degrees. Formula from handoff.md: atan2(sqrt(ax² + ay²), az).
    """
    if ax is None or ay is None or az is None:
        return None
    return math.degrees(math.atan2(math.sqrt(ax * ax + ay * ay), az))


def tilt_change(
    angle_x: float | None,
    angle_y: float | None,
    baseline_x: float | None,
    baseline_y: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Change in inclination since the node's baseline, in degrees.

    Returns (change_x, change_y, total), where total = sqrt(dx² + dy²).
    All three are None until the node has a baseline.
    """
    dx = angle_x - baseline_x if angle_x is not None and baseline_x is not None else None
    dy = angle_y - baseline_y if angle_y is not None and baseline_y is not None else None
    total = math.sqrt(dx * dx + dy * dy) if dx is not None and dy is not None else None
    return dx, dy, total


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def displacement_m(
    lat: float | None, lon: float | None, ref_lat: float | None, ref_lon: float | None
) -> float | None:
    """Horizontal distance from the node's reference position (coarse: GPS is only metre-accurate)."""
    if None in (lat, lon, ref_lat, ref_lon):
        return None
    return haversine_m(ref_lat, ref_lon, lat, lon)


def derive(
    values: Mapping[str, float | None],
    baseline_x: float | None = None,
    baseline_y: float | None = None,
    ref_lat: float | None = None,
    ref_lon: float | None = None,
) -> dict[str, float | None]:
    """Compute every derived field from one reading's raw values."""
    g = values.get
    dx, dy, total = tilt_change(g("angle_x"), g("angle_y"), baseline_x, baseline_y)
    return {
        "tilt_change_x": dx,
        "tilt_change_y": dy,
        "tilt_change_total": total,
        "slope_angle": slope_angle_deg(g("acc_x"), g("acc_y"), g("acc_z")),
        "acc_magnitude": magnitude(g("acc_x"), g("acc_y"), g("acc_z")),
        "gyro_magnitude": magnitude(g("gyro_x"), g("gyro_y"), g("gyro_z")),
        "mag_magnitude": magnitude(g("mag_x"), g("mag_y"), g("mag_z")),
        "displacement_m": displacement_m(g("lat"), g("lon"), ref_lat, ref_lon),
    }


def reading_values(reading) -> dict[str, float | None]:
    """Raw field values of a Reading row as a plain dict."""
    return {f: getattr(reading, f) for f in RAW_FIELDS}


def all_values(reading, node) -> dict[str, float | None]:
    """Raw + derived values for a Reading, using the node's baseline and reference position."""
    raw = reading_values(reading)
    raw.update(
        derive(raw, node.baseline_angle_x, node.baseline_angle_y, node.ref_lat, node.ref_lon)
    )
    return raw
