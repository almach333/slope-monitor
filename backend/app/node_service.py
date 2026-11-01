"""Helpers that build the node information the API returns.

Node status is computed, never stored (handoff.md section 5):
- "offline" if there is no reading for more than 3 x expected_interval_s
  (or the node has never sent data),
- otherwise "critical", then "warning", then "ok", from its active alerts.
"""

import hashlib
import secrets
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import alerts, derived
from app.models import Alert, Node, Reading
from app.schemas import LatestReading, NodeCounts, NodeOut


# ---------------------------------------------------------------- API keys


def generate_api_key() -> str:
    """A new random ingest key (shown to the user once)."""
    return secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    """SHA-256 of the key. Keys are long and random, so a fast hash is safe
    here (unlike passwords, which need a slow hash like argon2)."""
    return hashlib.sha256(key.encode()).hexdigest()


# ---------------------------------------------------------------- status


def node_status(node: Node, last_seen: datetime | None, active_counts: dict[str, int], now: datetime) -> str:
    if last_seen is None or now - last_seen > alerts.offline_threshold(node):
        return "offline"
    if active_counts.get("critical"):
        return "critical"
    if active_counts.get("warning"):
        return "warning"
    return "ok"


def latest_reading(db: Session, node_id: int) -> Reading | None:
    return db.scalars(
        select(Reading).where(Reading.node_id == node_id).order_by(Reading.ts.desc()).limit(1)
    ).first()


def active_alert_counts(db: Session) -> dict[int, dict[str, int]]:
    """{node_id: {"warning": n, "critical": n}} for open + acknowledged alerts."""
    rows = db.execute(
        select(Alert.node_id, Alert.level, func.count())
        .where(Alert.status.in_(alerts.ACTIVE_STATUSES))
        .group_by(Alert.node_id, Alert.level)
    ).all()
    counts: dict[int, dict[str, int]] = {}
    for node_id, level, n in rows:
        counts.setdefault(node_id, {"warning": 0, "critical": 0})[level] = n
    return counts


def to_latest(reading: Reading | None, node: Node) -> LatestReading | None:
    if reading is None:
        return None
    return LatestReading(
        ts=reading.ts,
        received_at=reading.received_at,
        seq=reading.seq,
        values=derived.all_values(reading, node),
        quality_flags=reading.quality_flags or [],
    )


def build_node_out(
    db: Session, node: Node, now: datetime, counts_by_node: dict[int, dict[str, int]] | None = None
) -> NodeOut:
    if counts_by_node is None:
        counts_by_node = active_alert_counts(db)
    latest = latest_reading(db, node.id)
    counts = counts_by_node.get(node.id, {"warning": 0, "critical": 0})
    last_seen = latest.ts if latest else None
    return NodeOut(
        id=node.id,
        name=node.name,
        dev_eui=node.dev_eui,
        description=node.description,
        ref_lat=node.ref_lat,
        ref_lon=node.ref_lon,
        baseline_angle_x=node.baseline_angle_x,
        baseline_angle_y=node.baseline_angle_y,
        baseline_slope_angle=node.baseline_slope_angle,
        baseline_set_at=node.baseline_set_at,
        expected_interval_s=node.expected_interval_s,
        created_at=node.created_at,
        is_active=node.is_active,
        status=node_status(node, last_seen, counts, now),
        last_seen=last_seen,
        latest=to_latest(latest, node),
        active_alerts=counts,
    )


def list_node_outs(db: Session, now: datetime) -> list[NodeOut]:
    counts = active_alert_counts(db)
    nodes = db.scalars(select(Node).order_by(Node.name)).all()
    return [build_node_out(db, n, now, counts) for n in nodes]


def node_counts(db: Session, node: Node) -> NodeCounts:
    """Uplinks received, flagged readings, and estimated missed uplinks.

    Missed uplinks use the packet counter (seq) when the node sends one.
    Without it, they are estimated from time gaps longer than 1.5 x the
    expected interval.
    """
    rows = db.execute(
        select(Reading.ts, Reading.seq).where(Reading.node_id == node.id).order_by(Reading.ts)
    ).all()
    flagged = db.scalar(
        select(func.count()).where(Reading.node_id == node.id, Reading.has_flags.is_(True))
    )
    missed = 0
    interval = node.expected_interval_s
    for (prev_ts, prev_seq), (ts, seq) in zip(rows, rows[1:]):
        if prev_seq is not None and seq is not None and seq > prev_seq:
            missed += seq - prev_seq - 1
        else:
            gap = (ts - prev_ts).total_seconds()
            if gap > 1.5 * interval:
                missed += int(gap // interval) - 1
    return NodeCounts(uplinks=len(rows), flagged=flagged or 0, missed=missed)
