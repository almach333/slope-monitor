"""The ONE internal ingest function (handoff.md sections 6 and 12).

Every way data can arrive (the simulator today; a LoRaWAN webhook or a
serial bridge later) must call `ingest_readings()` / `ingest_reading()`.

Ingest flow for each reading:
 1. (the router has already checked the node's API key)
 2. validate types (done by Pydantic in schemas.ReadingIn)
 3. range checks and spike check: bad values are FLAGGED but still stored
 4. duplicates (same node + timestamp) are skipped, not stored twice
 5. derived values are computed (on the fly, in derived.py)
 6. alert rules are evaluated, but only for the node's newest reading,
    so late or out-of-order packets can't confuse the debounce logic
 7. the result is returned (the router turns it into 201 / 200)
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import alerts, baseline, derived, quality
from app.models import Alert, AlertRule, Node, Reading
from app.schemas import IngestResult, ReadingIn

# How many recent readings we keep in memory while ingesting. Must be bigger
# than any rule's consecutive_readings plus room for flagged readings.
WINDOW_SIZE = 60

# Readings timestamped further in the future than this are rejected.
MAX_FUTURE = timedelta(minutes=5)


class IngestError(Exception):
    """Raised for a request that must be refused as a whole (e.g. inactive node)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def _last_valid_angles(window: list[Reading]) -> tuple[float | None, float | None]:
    """angle_x / angle_y of the most recent reading whose tilt is not flagged."""
    for r in reversed(window):
        if r.angle_x is None or r.angle_y is None:
            continue
        if {"angle_x", "angle_y"} & quality.invalid_fields(r.quality_flags):
            continue
        return r.angle_x, r.angle_y
    return None, None


class ValueCache:
    """Remembers each reading's raw + derived values and invalid fields during one batch.

    Several rules look at the same recent readings, so this avoids
    recomputing them. Must be cleared when the node's baseline changes.
    """

    def __init__(self, node: Node):
        self.node = node
        self._cache: dict[Reading, tuple[dict, set[str]]] = {}

    def get(self, reading: Reading) -> tuple[dict, set[str]]:
        if reading not in self._cache:
            self._cache[reading] = (
                derived.all_values(reading, self.node),
                quality.invalid_fields(reading.quality_flags),
            )
        return self._cache[reading]

    def clear(self) -> None:
        self._cache.clear()


def _recent_valid_values(window: list[Reading], cache: ValueCache, parameter: str, k: int) -> list[float]:
    """The last `k` valid values of `parameter` (oldest first), skipping flagged readings."""
    found: list[float] = []
    for r in reversed(window):
        values, bad = cache.get(r)
        if parameter in bad:
            continue
        value = values.get(parameter)
        if value is None:
            continue
        found.append(value)
        if len(found) == k:
            break
    found.reverse()
    return found


def _evaluate_rules(
    db: Session,
    node: Node,
    rules: list[AlertRule],
    active: dict[int, Alert],
    window: list[Reading],
    cache: ValueCache,
    at: datetime,
) -> None:
    """Evaluate every enabled rule of the node after a new reading."""
    for rule in rules:
        if not rule.enabled or rule.warning_threshold is None or rule.critical_threshold is None:
            continue  # disabled, or "pending baseline"
        values = _recent_valid_values(window, cache, rule.parameter, rule.consecutive_readings)
        current = active.get(rule.id)
        new_level = alerts.target_level(
            values,
            rule.comparator,
            rule.warning_threshold,
            rule.critical_threshold,
            rule.consecutive_readings,
            current.level if current else None,
        )
        latest_value = values[-1] if values else None
        new_active = alerts.apply_rule_level(db, node, rule, current, new_level, latest_value, at)
        if new_active is None:
            active.pop(rule.id, None)
        else:
            active[rule.id] = new_active


def _maybe_auto_baseline(
    db: Session, node: Node, window: list[Reading], cache: ValueCache, at: datetime
) -> None:
    """Set the baseline / reference position from the first valid readings if not set yet."""
    n = baseline.AUTO_BASELINE_READINGS
    if node.baseline_angle_x is None or node.baseline_angle_y is None:
        result = baseline.compute_baseline(window, n)
        if result is not None:
            baseline.apply_baseline(db, node, *result, at=at, user_id=None)
            cache.clear()  # derived tilt values depend on the baseline
    if node.ref_lat is None or node.ref_lon is None:
        pos = baseline.compute_reference_position(window, n)
        if pos is not None:
            node.ref_lat, node.ref_lon = pos
            cache.clear()  # displacement depends on the reference position


def ingest_readings(db: Session, node: Node, payloads: list[ReadingIn], now: datetime) -> IngestResult:
    """Store a batch of readings for one node and run the alert engine. Commits once at the end."""
    if not node.is_active:
        raise IngestError(403, "Node is deactivated")

    result = IngestResult()

    # Work out each reading's timestamp, reject ones too far in the future,
    # and sort oldest first so the debounce logic sees them in order.
    timed: list[tuple[datetime, ReadingIn]] = []
    for p in payloads:
        ts = p.ts or now
        if ts > now + MAX_FUTURE:
            result.rejected += 1
            result.errors.append(f"ts {ts.isoformat()} is in the future")
            continue
        timed.append((ts, p))
    timed.sort(key=lambda item: item[0])
    if not timed:
        return result

    # Timestamps already stored for this node (to skip duplicates).
    existing = set(
        db.scalars(
            select(Reading.ts).where(
                Reading.node_id == node.id,
                Reading.ts >= timed[0][0],
                Reading.ts <= timed[-1][0],
            )
        ).all()
    )

    # Recent readings (oldest first) and the current alert state.
    window = list(
        reversed(
            db.scalars(
                select(Reading)
                .where(Reading.node_id == node.id)
                .order_by(Reading.ts.desc())
                .limit(WINDOW_SIZE)
            ).all()
        )
    )
    latest_ts = window[-1].ts if window else None
    rules = list(node.rules)
    active = alerts.active_rule_alerts(db, node.id)
    offline_alert = alerts.active_offline_alert(db, node.id)
    cache = ValueCache(node)

    for ts, p in timed:
        if ts in existing:
            result.duplicates += 1
            continue
        existing.add(ts)

        values = {f: getattr(p, f) for f in derived.RAW_FIELDS}
        reading = Reading(node_id=node.id, ts=ts, received_at=now, seq=p.seq, **values)

        # Data quality checks: flag, never drop.
        flags = quality.check_ranges(values)
        is_newest = latest_ts is None or ts > latest_ts
        if is_newest:
            prev_x, prev_y = _last_valid_angles(window)
            if "angle_x_out_of_range" not in flags and "angle_y_out_of_range" not in flags:
                if quality.is_spike(p.angle_x, p.angle_y, prev_x, prev_y):
                    flags.append(quality.SPIKE_FLAG)
        reading.quality_flags = flags
        reading.has_flags = bool(flags)
        db.add(reading)
        result.stored += 1
        if flags:
            result.flagged += 1

        if not is_newest:
            continue  # late packet: stored, but doesn't drive alerts

        # Data arrived: close the open offline alert, or (if there wasn't
        # one) record a long gap in the history as an already-resolved alert.
        gap_recorded = False
        if offline_alert is not None:
            prev_ts = window[-1].ts if window else None
            gap_recorded = alerts.resolve_offline(db, offline_alert, ts, prev_ts)
            offline_alert = None
        if not gap_recorded and window and ts - window[-1].ts > alerts.offline_threshold(node):
            alerts.record_offline_gap(db, node, window[-1].ts, ts)

        window.append(reading)
        if len(window) > WINDOW_SIZE:
            window.pop(0)
        latest_ts = ts

        _maybe_auto_baseline(db, node, window, cache, at=ts)
        _evaluate_rules(db, node, rules, active, window, cache, at=ts)

    db.commit()
    return result


def ingest_reading(db: Session, node: Node, payload: ReadingIn, now: datetime) -> IngestResult:
    """Convenience wrapper for a single reading."""
    result = ingest_readings(db, node, [payload], now)
    result.duplicate = result.duplicates == 1 and result.stored == 0
    return result
