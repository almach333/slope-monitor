"""Alert rule evaluation and alert state changes (handoff.md section 7, R5 and R7).

How a rule works:
- Each rule has a warning and a critical threshold ("stacked" alarm).
- A level only fires after `consecutive_readings` (K) valid readings in a row
  breach it (debounce). Flagged readings don't count.
- A rule has at most ONE active alert at a time:
    none -> warning -> critical   (escalation resolves the warning alert)
    critical -> warning           (de-escalation when K readings are below critical)
    warning/critical -> none      (auto-resolve after K normal readings)
- Alerts use the reading's timestamp, so backfilled history has correct times.

`target_level()` is a pure function (no database), which makes the rules
easy to test. The other functions apply its decision to the database.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alert_defaults import ALERT_PARAMETERS, OFFLINE_PARAMETER
from app.models import Alert, AlertRule, Node, Reading

ACTIVE_STATUSES = ("open", "acknowledged")
LEVEL_RANK = {None: 0, "warning": 1, "critical": 2}

# A node is offline after this many missed expected intervals.
OFFLINE_FACTOR = 3


def breaches(value: float, threshold: float, comparator: str) -> bool:
    """True if the value is on the wrong side of the threshold."""
    return value > threshold if comparator == "gt" else value < threshold


def target_level(
    values: list[float],
    comparator: str,
    warning: float,
    critical: float,
    k: int,
    current: str | None,
) -> str | None:
    """Decide which level a rule should be at, given its last K valid values.

    `values` are the most recent valid values (at least K of them to decide;
    with fewer, nothing changes). `current` is the level of the rule's active
    alert, or None if it has none. Returns "critical", "warning" or None.
    """
    if len(values) < k:
        return current  # not enough data yet: keep whatever state we're in
    last_k = values[-k:]
    all_critical = all(breaches(v, critical, comparator) for v in last_k)
    all_warning = all(breaches(v, warning, comparator) for v in last_k)
    none_critical = not any(breaches(v, critical, comparator) for v in last_k)
    none_warning = not any(breaches(v, warning, comparator) for v in last_k)

    if all_critical:
        return "critical"
    if current == "critical":
        if not none_critical:
            return "critical"  # still some critical values: stay critical
        return None if none_warning else "warning"
    if current == "warning":
        return None if none_warning else "warning"
    # No active alert yet.
    return "warning" if all_warning else None


def format_value(parameter: str, value: float | None) -> str:
    info = ALERT_PARAMETERS.get(parameter, {"label": parameter, "unit": ""})
    if value is None:
        return "n/a"
    return f"{value:.2f}{info['unit']}"


def rule_message(rule: AlertRule, level: str, value: float, threshold: float) -> str:
    label = ALERT_PARAMETERS.get(rule.parameter, {"label": rule.parameter})["label"]
    sign = ">" if rule.comparator == "gt" else "<"
    return (
        f"{label} {format_value(rule.parameter, value)} {sign} {level} "
        f"{format_value(rule.parameter, threshold)} ({rule.consecutive_readings} consecutive readings)"
    )


def apply_rule_level(
    db: Session,
    node: Node,
    rule: AlertRule,
    active: Alert | None,
    new_level: str | None,
    latest_value: float | None,
    at: datetime,
) -> Alert | None:
    """Move a rule's alert to `new_level`. Returns the rule's new active alert (or None)."""
    current = active.level if active else None
    if new_level == current:
        return active

    if active is not None:
        active.status = "resolved"
        active.resolved_at = at
        if LEVEL_RANK[new_level] > LEVEL_RANK[current]:
            active.resolution_note = f"Escalated to {new_level}"
        elif new_level is not None:
            active.resolution_note = f"De-escalated to {new_level}"
        else:
            active.resolution_note = "Returned to normal"

    if new_level is None:
        return None

    threshold = rule.critical_threshold if new_level == "critical" else rule.warning_threshold
    alert = Alert(
        node_id=node.id,
        rule_id=rule.id,
        level=new_level,
        parameter=rule.parameter,
        value=latest_value,
        threshold=threshold,
        message=rule_message(rule, new_level, latest_value, threshold),
        status="open",
        opened_at=at,
    )
    db.add(alert)
    return alert


def active_rule_alerts(db: Session, node_id: int) -> dict[int, Alert]:
    """Active (open or acknowledged) rule alerts for a node, keyed by rule id."""
    rows = db.scalars(
        select(Alert).where(
            Alert.node_id == node_id,
            Alert.rule_id.is_not(None),
            Alert.status.in_(ACTIVE_STATUSES),
        )
    ).all()
    return {a.rule_id: a for a in rows}


def active_offline_alert(db: Session, node_id: int) -> Alert | None:
    return db.scalars(
        select(Alert).where(
            Alert.node_id == node_id,
            Alert.parameter == OFFLINE_PARAMETER,
            Alert.status.in_(ACTIVE_STATUSES),
        )
    ).first()


def offline_threshold(node: Node) -> timedelta:
    return timedelta(seconds=OFFLINE_FACTOR * node.expected_interval_s)


def offline_message(node: Node, silent_s: float) -> str:
    return (
        f"No data from {node.name} for {silent_s / 60:.1f} min "
        f"(expected every {node.expected_interval_s} s)"
    )


def resolve_offline(db: Session, alert: Alert, ts: datetime, prev_ts: datetime | None) -> bool:
    """Close an offline alert because data has arrived again. Returns True if resolved.

    The alert is premature if the node actually has data the offline
    checker hadn't seen yet: the new reading was measured before the
    alert's offline time, or the previous reading is newer than the
    "last seen" time the alert was based on (e.g. the checker ran while a
    backfill batch was still being saved). A premature alert is removed
    (returns False).
    """
    last_seen_at_alert = alert.opened_at - timedelta(seconds=alert.threshold or 0)
    if ts < alert.opened_at or (prev_ts is not None and prev_ts > last_seen_at_alert):
        db.delete(alert)
        return False
    alert.status = "resolved"
    alert.resolved_at = ts
    alert.resolution_note = "Data resumed"
    return True


def record_offline_gap(db: Session, node: Node, prev_ts: datetime, ts: datetime) -> None:
    """Record a long gap that no live offline alert covered, as an already-resolved alert.

    This happens for gaps in backfilled history, or if the server was
    stopped during an outage, so the gap still shows in the alert history.
    """
    silent_s = (ts - prev_ts).total_seconds()
    threshold_s = offline_threshold(node).total_seconds()
    db.add(
        Alert(
            node_id=node.id,
            rule_id=None,
            level="warning",
            parameter=OFFLINE_PARAMETER,
            value=silent_s,
            threshold=threshold_s,
            message=offline_message(node, silent_s),
            status="resolved",
            opened_at=prev_ts + offline_threshold(node),
            resolved_at=ts,
            resolution_note="Data resumed",
        )
    )


def check_offline_nodes(db: Session, now: datetime) -> int:
    """Open an offline alert for every active node that has gone quiet.

    Runs every 30 s in the background (see main.py). Returns how many new
    offline alerts were opened. Nodes that have never sent data are shown
    as offline but don't raise an alert.
    """
    last_ts_by_node = dict(
        db.execute(select(Reading.node_id, func.max(Reading.ts)).group_by(Reading.node_id)).all()
    )
    opened = 0
    for node in db.scalars(select(Node).where(Node.is_active.is_(True))).all():
        last_ts = last_ts_by_node.get(node.id)
        if last_ts is None:
            continue
        # SQLite's max() returns a naive value; make sure it's UTC-aware.
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        silent = now - last_ts
        if silent <= offline_threshold(node):
            continue
        if active_offline_alert(db, node.id) is not None:
            continue
        db.add(
            Alert(
                node_id=node.id,
                rule_id=None,
                level="warning",
                parameter=OFFLINE_PARAMETER,
                value=silent.total_seconds(),
                threshold=offline_threshold(node).total_seconds(),
                message=offline_message(node, silent.total_seconds()),
                status="open",
                opened_at=last_ts + offline_threshold(node),
            )
        )
        opened += 1
    db.commit()
    return opened
