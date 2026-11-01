"""Node behaviours for the simulator (handoff.md section 9).

Every value is a function of TIME (plus seeded random noise), not of the
previous value. That means backfill and live mode join up seamlessly, and
the same seed always gives the same data (useful for repeatable tests).

Scenarios (timeline measured in days since the start of the backfill, D = backfill length):
- stable       N1-N3: small noise around a fixed tilt, daily temperature and
                      humidity cycle, slow battery drain.
- creeping     N4: tilt creeps slowly, then accelerates over the last ~2 days
                   (progressive failure). Crosses 1° (warning) at about D-0.8 days
                   and 2° (critical) at about D-0.2 days. GPS displacement grows.
- low_battery  N5: battery drains fast: below 20 % at D-1.5 days, below 10 % at D-0.5.
- faulty       N6: occasional spike readings, ~5 % dropped packets, a 2-hour
                   outage in the backfilled history, and in live mode a short
                   outage every 30 minutes (longer than the offline threshold).
"""

import math
import random
from datetime import datetime, timedelta, timezone

from config import N6_OUTAGE_EVERY_MIN, N6_OUTAGE_LENGTH_MIN, SITE_CENTRE

EARTH_RADIUS_M = 6_371_000.0
SITE_UTC_OFFSET_H = 10  # local time at the placeholder site (AEST), for the daily cycle


def offset_position(east_m: float, north_m: float) -> tuple[float, float]:
    """Lat/lon of a point east_m / north_m metres from the site centre."""
    lat0, lon0 = SITE_CENTRE
    dlat = math.degrees(north_m / EARTH_RADIUS_M)
    dlon = math.degrees(east_m / (EARTH_RADIUS_M * math.cos(math.radians(lat0))))
    return lat0 + dlat, lon0 + dlon


def gravity_from_angles(angle_x: float, angle_y: float) -> tuple[float, float, float]:
    """Accelerometer reading (in g) for a node at rest at the given angles.

    Generating angles first and deriving gravity from them keeps the
    slope angle and the acceleration consistent with each other.
    """
    tx, ty = math.radians(angle_x), math.radians(angle_y)
    return math.sin(tx), math.sin(ty) * math.cos(tx), math.cos(tx) * math.cos(ty)


def creep_tilt(t_days: float, days: float) -> float:
    """N4 tilt change (degrees): slow linear creep, then exponential acceleration.

    Tuned so that for a 7-day backfill it passes 1° at ~day 6.2 and 2° at ~day 6.8.
    Capped at 5° so live mode stays realistic.
    """
    linear = 0.08 * t_days
    u = t_days - (days - 2.0)  # days since acceleration started
    accel = 0.085 * (math.exp(u / 0.62) - 1.0) if u > 0 else 0.0
    return min(linear + accel, 5.0)


def battery_level(scenario: str, t_days: float, days: float, start: float) -> float:
    if scenario == "low_battery":
        knee = days - 1.5
        if t_days <= knee:
            pct = 100.0 - 80.0 * (t_days / knee)
        else:
            pct = 20.0 - 10.0 * (t_days - knee)
        return max(pct, 5.0)
    return max(start - 0.3 * t_days, 5.0)  # slow drain, ~0.3 % per day


def is_n6_backfill_outage(t_days: float, days: float) -> bool:
    """A 2-hour outage about 3 days before the end of the backfill."""
    start = days - 3.0
    return start <= t_days < start + 2.0 / 24.0


def is_n6_live_outage(ts: datetime) -> bool:
    """In live mode, N6 goes quiet for a few minutes every half hour."""
    minute_of_cycle = int(ts.timestamp() // 60) % N6_OUTAGE_EVERY_MIN
    return minute_of_cycle < N6_OUTAGE_LENGTH_MIN


def sample(
    node: dict,
    ts: datetime,
    t0: datetime,
    days: float,
    seed: int,
    live: bool,
) -> dict | None:
    """One reading for `node` at time `ts`, or None if the packet is not received."""
    rng = random.Random(f"{seed}-{node['dev_eui']}-{int(ts.timestamp())}")
    scenario = node["scenario"]
    t_days = (ts - t0).total_seconds() / 86400.0

    # --- Faulty node: dropped packets and outages.
    if scenario == "faulty":
        if rng.random() < 0.05:
            return None
        if is_n6_backfill_outage(t_days, days):
            return None
        if live and is_n6_live_outage(ts):
            return None

    # --- Tilt (degrees). Change is split 80 % / 60 % between the axes,
    # so the total change sqrt(0.8² + 0.6²) = 1.0 x tilt.
    tilt = creep_tilt(t_days, days) if scenario == "creeping" else 0.0
    angle_x = node["base_angle_x"] + 0.8 * tilt + rng.gauss(0, 0.02)
    angle_y = node["base_angle_y"] + 0.6 * tilt + rng.gauss(0, 0.02)

    # --- Acceleration from the angles (node at rest), plus sensor noise.
    gx, gy, gz = gravity_from_angles(angle_x, angle_y)
    acc_x, acc_y, acc_z = (g + rng.gauss(0, 0.001) for g in (gx, gy, gz))

    # --- Position: N4 slides downslope (east), 2.5 m per degree of tilt.
    # Consumer GPS noise of about a metre.
    slide_m = 2.5 * tilt
    lat, lon = offset_position(
        node["east_m"] + slide_m + rng.gauss(0, 0.8),
        node["north_m"] + rng.gauss(0, 0.8),
    )

    # --- Environment: daily cycle in site local time.
    local_hour = (ts.hour + ts.minute / 60 + SITE_UTC_OFFSET_H) % 24
    daily = math.sin(2 * math.pi * (local_hour - 9) / 24)  # warmest mid-afternoon
    temperature = 22.0 + 7.0 * daily + rng.gauss(0, 0.3)
    humidity = min(100.0, max(0.0, 62.0 - 18.0 * daily + rng.gauss(0, 1.0)))

    battery = battery_level(scenario, t_days, days, node.get("battery_start", 98.0)) + rng.gauss(0, 0.1)
    battery = min(100.0, max(0.0, battery))

    rssi = node["rssi_base"] + rng.gauss(0, 2.0)
    snr = max(-20.0, min(15.0, 9.0 + (rssi + 100.0) * 0.4 + rng.gauss(0, 1.0)))

    reading = {
        "dev_eui": node["dev_eui"],
        "ts": ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lat": round(lat, 7),
        "lon": round(lon, 7),
        "angle_x": round(angle_x, 3),
        "angle_y": round(angle_y, 3),
        "angle_z": round(node["heading"] + rng.gauss(0, 0.3), 2),
        "acc_x": round(acc_x, 4),
        "acc_y": round(acc_y, 4),
        "acc_z": round(acc_z, 4),
        # At rest the gyroscope reads ~0 °/s.
        "gyro_x": round(rng.gauss(0, 0.05), 3),
        "gyro_y": round(rng.gauss(0, 0.05), 3),
        "gyro_z": round(rng.gauss(0, 0.05), 3),
        # Earth's field (~50 µT total), roughly constant.
        "mag_x": round(22.0 + rng.gauss(0, 0.3), 2),
        "mag_y": round(5.0 + rng.gauss(0, 0.3), 2),
        "mag_z": round(-44.0 + rng.gauss(0, 0.3), 2),
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 1),
        "battery_pct": round(battery, 1),
        "battery_v": round(3.3 + 0.9 * battery / 100.0, 3),
        "rssi": round(rssi),
        "snr": round(snr, 1),
    }

    # --- Faulty node: occasional spikes the backend must flag.
    if scenario == "faulty":
        roll = rng.random()
        if roll < 0.01:
            reading["angle_x"] = rng.choice([99.0, -99.0])  # out of range
        elif roll < 0.02:
            reading["acc_z"] = 20.0  # out of range (±16 g)
        elif roll < 0.03:
            reading["angle_y"] = round(reading["angle_y"] + 15.0, 3)  # in range, but a >10° jump

    return reading


def timeline(start: datetime, end: datetime, interval_s: int) -> list[datetime]:
    """Evenly spaced timestamps from start (inclusive) to end (inclusive)."""
    out = []
    t = start
    step = timedelta(seconds=interval_s)
    while t <= end:
        out.append(t)
        t += step
    return out
