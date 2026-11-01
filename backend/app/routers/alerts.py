"""Alert list and acknowledge (handoff.md section 7)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db, utcnow
from app.models import Alert
from app.schemas import AlertOut, AlertPage

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def to_alert_out(alert: Alert) -> AlertOut:
    out = AlertOut.model_validate(alert)
    out.node_name = alert.node.name if alert.node else ""
    return out


@router.get("", response_model=AlertPage)
def list_alerts(
    _user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    status: Literal["open", "acknowledged", "resolved", "active"] | None = None,
    node_id: int | None = None,
    level: Literal["warning", "critical"] | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Alerts, newest first. `status=active` means open or acknowledged."""
    query = select(Alert)
    if status == "active":
        query = query.where(Alert.status.in_(("open", "acknowledged")))
    elif status:
        query = query.where(Alert.status == status)
    if node_id is not None:
        query = query.where(Alert.node_id == node_id)
    if level:
        query = query.where(Alert.level == level)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = Alert.resolved_at.desc() if status == "resolved" else Alert.opened_at.desc()
    rows = db.scalars(query.order_by(order, Alert.id.desc()).limit(limit).offset(offset)).all()
    return AlertPage(items=[to_alert_out(a) for a in rows], total=total or 0)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: int, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    """Mark an alert as seen. It stays active until the condition clears."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != "open":
        raise HTTPException(status_code=409, detail=f"Alert is already {alert.status}")
    alert.status = "acknowledged"
    alert.acknowledged_by = user.id
    alert.acknowledged_at = utcnow()
    db.commit()
    return to_alert_out(alert)
