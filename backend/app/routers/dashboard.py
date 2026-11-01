"""Dashboard summary: counts, every node's status and the active alerts."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts import ACTIVE_STATUSES
from app.auth import CurrentUser
from app.db import get_db, utcnow
from app.models import Alert
from app.node_service import list_node_outs
from app.routers.alerts import to_alert_out
from app.schemas import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(_user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    now = utcnow()
    nodes = list_node_outs(db, now)
    active = db.scalars(
        select(Alert).where(Alert.status.in_(ACTIVE_STATUSES)).order_by(Alert.opened_at.desc())
    ).all()
    offline = sum(1 for n in nodes if n.status == "offline")
    counts = {
        "nodes": len(nodes),
        "online": len(nodes) - offline,
        "offline": offline,
        "alerts_active": len(active),
        "alerts_new": sum(1 for a in active if a.status == "open"),
        "alerts_warning": sum(1 for a in active if a.level == "warning"),
        "alerts_critical": sum(1 for a in active if a.level == "critical"),
    }
    return DashboardSummary(
        server_time=now,
        counts=counts,
        nodes=nodes,
        active_alerts=[to_alert_out(a) for a in active],
    )
