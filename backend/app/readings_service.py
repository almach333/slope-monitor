"""Loading readings for charts: downsampling and gaps.

Charts never need more than a few hundred points, so long time ranges are
downsampled on the server with a time-bucket average. Missing data is shown
as a gap: a `null` point is inserted wherever two consecutive points are
further apart than max(3 x expected interval, 2 x bucket size), and the
chart doesn't draw a line across a null.
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import derived, quality
from app.models import Node, Reading


def load_points(
    db: Session,
    node: Node,
    start: datetime,
    end: datetime,
    fields: list[str],
    include_flagged: bool,
    max_points: int,
) -> tuple[int, list[dict]]:
    """Return (bucket size in seconds, points) for one node between start and end.

    Each point is {"ts": datetime, "flagged": bool, <field>: float | None}.
    Flagged values are left out (set to None) unless include_flagged is True.
    A bucket size of 0 means the raw readings were returned (no averaging).
    """
    # Select plain columns rather than full ORM objects: much faster for the
    # thousands of rows a 7-day chart needs. Rows still allow `row.angle_x`.
    columns = [Reading.ts, Reading.quality_flags] + [getattr(Reading, f) for f in derived.RAW_FIELDS]
    rows = db.execute(
        select(*columns)
        .where(Reading.node_id == node.id, Reading.ts >= start, Reading.ts <= end)
        .order_by(Reading.ts)
    ).all()

    # 1. Raw points with derived values; hide flagged values unless asked.
    raw_points = []
    for r in rows:
        values = derived.all_values(r, node)
        bad = quality.invalid_fields(r.quality_flags) if not include_flagged else set()
        point = {"ts": r.ts, "flagged": bool(r.quality_flags)}
        for f in fields:
            point[f] = None if f in bad else values.get(f)
        raw_points.append(point)

    # 2. Downsample if there are too many points.
    bucket_s = 0
    points = raw_points
    if len(raw_points) > max_points:
        bucket_s = max(1, math.ceil((end - start).total_seconds() / max_points))
        points = _bucket_average(raw_points, fields, start, bucket_s)

    # 3. Insert gaps.
    gap_limit = max(3 * node.expected_interval_s, 2 * bucket_s)
    return bucket_s, _insert_gaps(points, fields, gap_limit)


def _bucket_average(points: list[dict], fields: list[str], start: datetime, bucket_s: int) -> list[dict]:
    """Average points into fixed-width time buckets (ignoring missing values)."""
    buckets: dict[int, list[dict]] = {}
    for p in points:
        index = int((p["ts"] - start).total_seconds() // bucket_s)
        buckets.setdefault(index, []).append(p)

    result = []
    for index in sorted(buckets):
        members = buckets[index]
        out = {
            # Timestamp at the middle of the bucket.
            "ts": start + timedelta(seconds=index * bucket_s + bucket_s / 2),
            "flagged": any(m["flagged"] for m in members),
        }
        for f in fields:
            vals = [m[f] for m in members if m[f] is not None]
            out[f] = sum(vals) / len(vals) if vals else None
        result.append(out)
    return result


def _insert_gaps(points: list[dict], fields: list[str], gap_limit_s: float) -> list[dict]:
    if not points:
        return points
    result = [points[0]]
    for prev, cur in zip(points, points[1:]):
        if (cur["ts"] - prev["ts"]).total_seconds() > gap_limit_s:
            gap = {"ts": prev["ts"] + timedelta(seconds=1), "flagged": False, "gap": True}
            gap.update({f: None for f in fields})
            result.append(gap)
        result.append(cur)
    return result


def parse_fields(fields: str | None) -> list[str]:
    """Turn "a,b,c" into a validated list of field names (default: all)."""
    if not fields:
        return list(derived.ALL_FIELDS)
    wanted = [f.strip() for f in fields.split(",") if f.strip()]
    unknown = [f for f in wanted if f not in derived.ALL_FIELDS]
    if unknown:
        raise ValueError(f"Unknown fields: {', '.join(unknown)}")
    return wanted
