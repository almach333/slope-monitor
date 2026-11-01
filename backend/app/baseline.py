"""Tilt baseline and reference position.

The baseline is the node's "normal" inclination; tilt change is measured
from it. It is set automatically from the median of the first valid
readings, or manually from the most recent ones ("Set baseline now").
Using the median ignores the odd noisy value.

When the baseline changes, baseline-relative rules (slope angle) get new
absolute thresholds: threshold = baseline slope angle + offset.
"""

from collections.abc import Sequence
from datetime import datetime
from statistics import median

from sqlalchemy.orm import Session

from app import derived, quality
from app.models import AlertRule, AlertRuleChange, Node, Reading

AUTO_BASELINE_READINGS = 10


def compute_baseline(readings: Sequence[Reading], n: int) -> tuple[float, float, float] | None:
    """Median angle_x, angle_y and slope angle of the first `n` valid readings given.

    Returns None if there are fewer than `n` usable readings.
    """
    xs, ys, slopes = [], [], []
    for r in readings:
        bad = quality.invalid_fields(r.quality_flags)
        slope = derived.slope_angle_deg(r.acc_x, r.acc_y, r.acc_z)
        if (
            r.angle_x is None or r.angle_y is None or slope is None
            or {"angle_x", "angle_y", "slope_angle"} & bad
        ):
            continue
        xs.append(r.angle_x)
        ys.append(r.angle_y)
        slopes.append(slope)
        if len(xs) == n:
            break
    if len(xs) < n:
        return None
    return median(xs), median(ys), median(slopes)


def compute_reference_position(readings: Sequence[Reading], n: int) -> tuple[float, float] | None:
    """Median lat/lon of the first `n` valid GPS fixes given, or None if not enough."""
    lats, lons = [], []
    for r in readings:
        if r.lat is None or r.lon is None or {"lat", "lon"} & quality.invalid_fields(r.quality_flags):
            continue
        lats.append(r.lat)
        lons.append(r.lon)
        if len(lats) == n:
            break
    if len(lats) < n:
        return None
    return median(lats), median(lons)


def rule_snapshot(rule: AlertRule) -> dict:
    """The editable fields of a rule, for the audit history."""
    return {
        "parameter": rule.parameter,
        "comparator": rule.comparator,
        "warning_threshold": rule.warning_threshold,
        "critical_threshold": rule.critical_threshold,
        "warning_offset": rule.warning_offset,
        "critical_offset": rule.critical_offset,
        "consecutive_readings": rule.consecutive_readings,
        "enabled": rule.enabled,
    }


def apply_baseline(
    db: Session,
    node: Node,
    angle_x: float,
    angle_y: float,
    slope_angle: float,
    at: datetime,
    user_id: int | None = None,
) -> list[AlertRule]:
    """Store a new baseline and update baseline-relative rule thresholds.

    Returns the rules whose thresholds changed.
    """
    node.baseline_angle_x = angle_x
    node.baseline_angle_y = angle_y
    node.baseline_slope_angle = slope_angle
    node.baseline_set_at = at

    changed = []
    for rule in node.rules:
        if rule.warning_offset is None or rule.critical_offset is None:
            continue
        old = rule_snapshot(rule)
        rule.warning_threshold = round(slope_angle + rule.warning_offset, 4)
        rule.critical_threshold = round(slope_angle + rule.critical_offset, 4)
        rule.updated_at = at
        rule.updated_by = user_id
        db.add(
            AlertRuleChange(
                rule_id=rule.id,
                node_id=node.id,
                action="baseline",
                changed_by=user_id,
                changed_at=at,
                old_values=old,
                new_values=rule_snapshot(rule),
                justification=(
                    f"Baseline set: slope angle {slope_angle:.2f}°, thresholds = baseline + "
                    f"{rule.warning_offset:g}° / +{rule.critical_offset:g}°"
                ),
            )
        )
        changed.append(rule)
    return changed
