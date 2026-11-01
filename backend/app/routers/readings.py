"""Readings across nodes: paginated table, multi-node series and CSV export."""

import csv
import io
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import derived, readings_service
from app.auth import CurrentUser
from app.db import get_db
from app.models import Node, Reading
from app.routers.nodes import resolve_range
from app.schemas import MultiSeries, ReadingPage, ReadingRow, SeriesLine

router = APIRouter(prefix="/api/readings", tags=["readings"])

DB = Annotated[Session, Depends(get_db)]
From = Annotated[datetime | None, Query(alias="from")]
To = Annotated[datetime | None, Query(alias="to")]


def parse_node_ids(db: Session, node_ids: str | None) -> list[Node]:
    """Turn "1,2,3" into Node objects (default: all nodes)."""
    if not node_ids:
        return list(db.scalars(select(Node).order_by(Node.name)).all())
    try:
        ids = [int(x) for x in node_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="node_ids must be a comma-separated list of numbers")
    nodes = list(db.scalars(select(Node).where(Node.id.in_(ids)).order_by(Node.name)).all())
    if len(nodes) != len(set(ids)):
        raise HTTPException(status_code=404, detail="One or more nodes not found")
    return nodes


@router.get("", response_model=ReadingPage)
def list_readings(
    _user: CurrentUser,
    db: DB,
    node_ids: str | None = None,
    start: From = None,
    end: To = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Raw readings (newest first) with derived values, for the Results table."""
    nodes = parse_node_ids(db, node_ids)
    start, end = resolve_range(start, end)
    by_id = {n.id: n for n in nodes}
    query = select(Reading).where(
        Reading.node_id.in_(by_id), Reading.ts >= start, Reading.ts <= end
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Reading.ts.desc(), Reading.node_id).limit(page_size).offset((page - 1) * page_size)
    ).all()
    items = [
        ReadingRow(
            id=r.id,
            node_id=r.node_id,
            node_name=by_id[r.node_id].name,
            ts=r.ts,
            received_at=r.received_at,
            seq=r.seq,
            values=derived.all_values(r, by_id[r.node_id]),
            quality_flags=r.quality_flags or [],
        )
        for r in rows
    ]
    return ReadingPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/series", response_model=MultiSeries, response_model_by_alias=True)
def series(
    _user: CurrentUser,
    db: DB,
    field: str,
    node_ids: str | None = None,
    start: From = None,
    end: To = None,
    max_points: int = Query(300, ge=10, le=5000),
    include_flagged: bool = False,
):
    """One field for several nodes (one line per node), downsampled for charts."""
    if field not in derived.ALL_FIELDS:
        raise HTTPException(status_code=422, detail=f"Unknown field: {field}")
    nodes = parse_node_ids(db, node_ids)
    start, end = resolve_range(start, end)
    lines = []
    bucket = 0
    for node in nodes:
        bucket_s, points = readings_service.load_points(
            db, node, start, end, [field], include_flagged, max_points
        )
        bucket = max(bucket, bucket_s)
        lines.append(
            SeriesLine(
                node_id=node.id,
                name=node.name,
                points=[{"ts": p["ts"], "v": p[field]} for p in points],
            )
        )
    return MultiSeries(field=field, from_=start, to=end, bucket_s=bucket, series=lines)


@router.get("/export")
def export_csv(_user: CurrentUser, db: DB, node_ids: str | None = None, start: From = None, end: To = None):
    """CSV download of every reading in the range, with derived values (R10)."""
    nodes = parse_node_ids(db, node_ids)
    start, end = resolve_range(start, end)
    by_id = {n.id: n for n in nodes}
    header = ["node", "dev_eui", "ts", "received_at", "seq", *derived.ALL_FIELDS, "quality_flags"]
    # Load the rows now, while the database session is definitely open.
    rows = db.scalars(
        select(Reading)
        .where(Reading.node_id.in_(by_id), Reading.ts >= start, Reading.ts <= end)
        .order_by(Reading.node_id, Reading.ts)
    ).all()

    def generate() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        for r in rows:
            node = by_id[r.node_id]
            values = derived.all_values(r, node)
            writer.writerow(
                [
                    node.name,
                    node.dev_eui,
                    r.ts.isoformat(),
                    r.received_at.isoformat(),
                    r.seq if r.seq is not None else "",
                    *("" if values[f] is None else round(values[f], 6) for f in derived.ALL_FIELDS),
                    ";".join(r.quality_flags or []),
                ]
            )
            if buffer.tell() > 64_000:
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    filename = f"readings_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
