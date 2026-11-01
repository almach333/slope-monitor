"""Alert rules: create, edit, delete and history (requirement R6).

Every change needs a justification and is recorded in AlertRuleChange,
so there is a full audit trail of who changed which limit, when and why.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alert_defaults import ALERT_PARAMETERS, DEFAULT_RULES, PLACEHOLDER_NOTE
from app.auth import CurrentUser
from app.baseline import rule_snapshot
from app.db import get_db, utcnow
from app.models import AlertRule, AlertRuleChange, Node, User
from app.schemas import (
    AlertDefaults,
    AlertRuleChangeOut,
    AlertRuleCreate,
    AlertRuleOut,
    AlertRuleUpdate,
    check_order,
)

router = APIRouter(prefix="/api", tags=["alert rules"])

DB = Annotated[Session, Depends(get_db)]


def to_rule_out(rule: AlertRule) -> AlertRuleOut:
    out = AlertRuleOut.model_validate(rule)
    out.pending_baseline = rule.warning_threshold is None or rule.critical_threshold is None
    return out


def _fill_from_baseline(node: Node, rule: AlertRule) -> None:
    """For baseline-relative rules, compute absolute thresholds if the node has a baseline."""
    if rule.warning_offset is None or rule.critical_offset is None:
        return
    if node.baseline_slope_angle is None:
        rule.warning_threshold = rule.critical_threshold = None  # pending baseline
    else:
        rule.warning_threshold = round(node.baseline_slope_angle + rule.warning_offset, 4)
        rule.critical_threshold = round(node.baseline_slope_angle + rule.critical_offset, 4)


def create_rule(db: Session, node: Node, body: AlertRuleCreate, user: User) -> AlertRule:
    """Create a rule and its 'created' history entry (used here and by node registration)."""
    now = utcnow()
    rule = AlertRule(
        node_id=node.id,
        parameter=body.parameter,
        comparator=body.comparator,
        warning_threshold=body.warning_threshold,
        critical_threshold=body.critical_threshold,
        warning_offset=body.warning_offset,
        critical_offset=body.critical_offset,
        consecutive_readings=body.consecutive_readings,
        justification=body.justification,
        enabled=body.enabled,
        updated_by=user.id,
        updated_at=now,
    )
    node.rules.append(rule)
    _fill_from_baseline(node, rule)
    db.flush()  # assigns rule.id
    db.add(
        AlertRuleChange(
            rule_id=rule.id,
            node_id=node.id,
            action="created",
            changed_by=user.id,
            changed_at=now,
            old_values=None,
            new_values=rule_snapshot(rule),
            justification=body.justification,
        )
    )
    return rule


def _get_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


def _get_rule(db: Session, node_id: int, rule_id: int) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None or rule.node_id != node_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.get("/alert-rules/defaults", response_model=AlertDefaults)
def defaults(_user: CurrentUser):
    """Default rules offered on the New Device page (placeholders, not engineering limits)."""
    return AlertDefaults(rules=DEFAULT_RULES, parameters=ALERT_PARAMETERS, note=PLACEHOLDER_NOTE)


@router.get("/nodes/{node_id}/alert-rules", response_model=list[AlertRuleOut])
def list_rules(node_id: int, _user: CurrentUser, db: DB):
    node = _get_node(db, node_id)
    return [to_rule_out(r) for r in sorted(node.rules, key=lambda r: r.id)]


@router.post("/nodes/{node_id}/alert-rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
def add_rule(node_id: int, body: AlertRuleCreate, user: CurrentUser, db: DB):
    node = _get_node(db, node_id)
    rule = create_rule(db, node, body, user)
    db.commit()
    return to_rule_out(rule)


@router.patch("/nodes/{node_id}/alert-rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(node_id: int, rule_id: int, body: AlertRuleUpdate, user: CurrentUser, db: DB):
    """Change a rule. A justification is required for every change (R6)."""
    node = _get_node(db, node_id)
    rule = _get_rule(db, node_id, rule_id)
    old = rule_snapshot(rule)
    changes = body.model_dump(exclude_unset=True, exclude={"justification"})

    # Setting absolute thresholds switches a baseline-relative rule to absolute.
    if "warning_threshold" in changes or "critical_threshold" in changes:
        if "warning_offset" not in changes and "critical_offset" not in changes:
            rule.warning_offset = rule.critical_offset = None
    for field, value in changes.items():
        setattr(rule, field, value)
    _fill_from_baseline(node, rule)

    # Re-check the combined result (e.g. critical still above warning).
    try:
        has_abs = rule.warning_threshold is not None and rule.critical_threshold is not None
        has_off = rule.warning_offset is not None and rule.critical_offset is not None
        if not has_abs and not has_off:
            raise ValueError("Give both warning and critical thresholds (or both baseline offsets)")
        if has_off and rule.parameter != "slope_angle":
            raise ValueError("Baseline offsets are only supported for the slope_angle parameter")
        check_order(rule.comparator, rule.warning_threshold, rule.critical_threshold, "threshold")
        check_order(rule.comparator, rule.warning_offset, rule.critical_offset, "offset")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))

    rule.justification = body.justification
    rule.updated_by = user.id
    rule.updated_at = utcnow()
    db.add(
        AlertRuleChange(
            rule_id=rule.id,
            node_id=node.id,
            action="updated",
            changed_by=user.id,
            changed_at=rule.updated_at,
            old_values=old,
            new_values=rule_snapshot(rule),
            justification=body.justification,
        )
    )
    db.commit()
    return to_rule_out(rule)


@router.delete("/nodes/{node_id}/alert-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    node_id: int,
    rule_id: int,
    user: CurrentUser,
    db: DB,
    justification: str = Query(min_length=10, description="Why this rule is being removed"),
):
    rule = _get_rule(db, node_id, rule_id)
    db.add(
        AlertRuleChange(
            rule_id=rule.id,
            node_id=node_id,
            action="deleted",
            changed_by=user.id,
            changed_at=utcnow(),
            old_values=rule_snapshot(rule),
            new_values=None,
            justification=justification.strip(),
        )
    )
    db.delete(rule)
    db.commit()


@router.get("/nodes/{node_id}/alert-rules/history", response_model=list[AlertRuleChangeOut])
def rule_history(node_id: int, _user: CurrentUser, db: DB):
    """Every change to this node's rules, newest first."""
    _get_node(db, node_id)
    rows = db.scalars(
        select(AlertRuleChange)
        .where(AlertRuleChange.node_id == node_id)
        .order_by(AlertRuleChange.changed_at.desc(), AlertRuleChange.id.desc())
    ).all()
    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    result = []
    for row in rows:
        out = AlertRuleChangeOut.model_validate(row)
        out.changed_by_name = names.get(row.changed_by) if row.changed_by else "System"
        result.append(out)
    return result
