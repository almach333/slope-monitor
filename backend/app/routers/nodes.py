"""Nodes: list, register, edit, baseline, API key and per-node readings."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import baseline, node_service, readings_service
from app.auth import CurrentUser
from app.db import get_db, utcnow
from app.models import Node, Reading
from app.routers.alert_rules import create_rule
from app.schemas import (
    ApiKeyOut,
    AlertRuleOut,
    BaselineRequest,
    NodeCreate,
    NodeCreated,
    NodeDetail,
    NodeOut,
    NodeUpdate,
    ReadingSeries,
)

router = APIRouter(prefix="/api/nodes", tags=["nodes"])

DB = Annotated[Session, Depends(get_db)]


def get_node_or_404(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


def resolve_range(start: datetime | None, end: datetime | None, default_hours: int = 24) -> tuple[datetime, datetime]:
    """Default to the last `default_hours` hours; check the range makes sense."""
    end = end or utcnow()
    start = start or end - timedelta(hours=default_hours)
    if start >= end:
        raise HTTPException(status_code=422, detail="'from' must be before 'to'")
    return start, end


@router.get("", response_model=list[NodeOut])
def list_nodes(_user: CurrentUser, db: DB):
    """All nodes with their status and latest reading (including derived values)."""
    return node_service.list_node_outs(db, utcnow())


@router.post("", response_model=NodeCreated, status_code=status.HTTP_201_CREATED)
def register_node(body: NodeCreate, user: CurrentUser, db: DB):
    """Register a node. The response contains its ingest API key, shown only this once."""
    if db.scalars(select(Node).where(Node.dev_eui == body.dev_eui)).first():
        raise HTTPException(status_code=409, detail="A node with this dev_eui already exists")
    api_key = node_service.generate_api_key()
    node = Node(
        name=body.name.strip(),
        dev_eui=body.dev_eui,
        description=body.description,
        ref_lat=body.ref_lat,
        ref_lon=body.ref_lon,
        expected_interval_s=body.expected_interval_s,
        api_key_hash=node_service.hash_api_key(api_key),
    )
    db.add(node)
    db.flush()  # assigns node.id
    for rule in body.rules:
        create_rule(db, node, rule, user)
    db.commit()
    return NodeCreated(node=node_service.build_node_out(db, node, utcnow()), api_key=api_key)


@router.get("/{node_id}", response_model=NodeDetail)
def get_node(node_id: int, _user: CurrentUser, db: DB):
    node = get_node_or_404(db, node_id)
    out = node_service.build_node_out(db, node, utcnow())
    return NodeDetail(**out.model_dump(), counts=node_service.node_counts(db, node))


@router.patch("/{node_id}", response_model=NodeOut)
def update_node(node_id: int, body: NodeUpdate, _user: CurrentUser, db: DB):
    """Edit name, description, reference position, interval, baseline angles or active flag."""
    node = get_node_or_404(db, node_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(node, field, value)
    if "baseline_angle_x" in changes or "baseline_angle_y" in changes:
        node.baseline_set_at = utcnow()
    db.commit()
    return node_service.build_node_out(db, node, utcnow())


@router.post("/{node_id}/baseline")
def set_baseline(node_id: int, body: BaselineRequest, user: CurrentUser, db: DB) -> dict:
    """Set the tilt baseline from the median of the last N valid readings.

    Also recalculates baseline-relative (slope angle) rule thresholds.
    """
    node = get_node_or_404(db, node_id)
    recent = db.scalars(
        select(Reading)
        .where(Reading.node_id == node.id)
        .order_by(Reading.ts.desc())
        .limit(body.readings * 3 + 20)
    ).all()
    result = baseline.compute_baseline(recent, body.readings)
    if result is None:
        raise HTTPException(
            status_code=409, detail=f"Not enough valid readings (need {body.readings}) to set a baseline"
        )
    changed = baseline.apply_baseline(db, node, *result, at=utcnow(), user_id=user.id)
    db.commit()
    return {
        "node": node_service.build_node_out(db, node, utcnow()),
        "updated_rules": [AlertRuleOut.model_validate(r) for r in changed],
    }


@router.post("/{node_id}/rotate-key", response_model=ApiKeyOut)
def rotate_key(node_id: int, _user: CurrentUser, db: DB):
    """Issue a new ingest API key (the old one stops working). Shown only once."""
    node = get_node_or_404(db, node_id)
    api_key = node_service.generate_api_key()
    node.api_key_hash = node_service.hash_api_key(api_key)
    db.commit()
    return ApiKeyOut(api_key=api_key)


@router.get("/{node_id}/readings", response_model=ReadingSeries, response_model_by_alias=True)
def node_readings(
    node_id: int,
    _user: CurrentUser,
    db: DB,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    fields: str | None = None,
    max_points: int = Query(500, ge=10, le=5000),
    include_flagged: bool = False,
):
    """Historical readings for charts, downsampled to at most `max_points`.

    `fields` is a comma-separated list (raw and/or derived names); default is all.
    """
    node = get_node_or_404(db, node_id)
    start, end = resolve_range(start, end)
    try:
        field_list = readings_service.parse_fields(fields)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    bucket_s, points = readings_service.load_points(
        db, node, start, end, field_list, include_flagged, max_points
    )
    return ReadingSeries(
        node_id=node.id, from_=start, to=end, bucket_s=bucket_s, fields=field_list, points=points
    )
