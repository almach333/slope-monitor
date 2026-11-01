"""R5 (alert when tilt exceeds a safe limit) and R7 (multiple alert levels as a safety measure)."""

from datetime import timedelta

from sqlalchemy import select

from app.alerts import check_offline_nodes, target_level
from app.models import Alert, Node
from tests.conftest import ingest, make_reading, register_node

TILT_RULE = {
    "parameter": "tilt_change_total",
    "comparator": "gt",
    "warning_threshold": 1.0,
    "critical_threshold": 2.0,
    "consecutive_readings": 3,
    "justification": "Test rule: placeholder thresholds",
}
BATTERY_RULE = {
    "parameter": "battery_pct",
    "comparator": "lt",
    "warning_threshold": 20.0,
    "critical_threshold": 10.0,
    "consecutive_readings": 3,
    "justification": "Test rule: placeholder thresholds",
}

# ------------------------------------------------------------------ pure decision logic


def test_no_alert_before_enough_consecutive_readings():
    """R7 (debounce): fewer than K breaching readings don't fire anything."""
    assert target_level([1.5, 1.5], "gt", 1.0, 2.0, k=3, current=None) is None


def test_warning_after_k_breaches():
    """R5/R7: K readings above the warning threshold open a warning."""
    assert target_level([1.5, 1.6, 1.7], "gt", 1.0, 2.0, k=3, current=None) == "warning"


def test_one_normal_reading_prevents_alarm():
    """R7: the breaches must be consecutive."""
    assert target_level([1.5, 0.5, 1.7], "gt", 1.0, 2.0, k=3, current=None) is None


def test_escalation_to_critical():
    """R7: the stacked alarm moves from warning to critical as the value worsens."""
    assert target_level([2.1, 2.2, 2.3], "gt", 1.0, 2.0, k=3, current="warning") == "critical"


def test_de_escalation_and_resolve():
    """R7: critical drops back to warning, and warning resolves after K normal readings."""
    assert target_level([1.5, 1.5, 1.5], "gt", 1.0, 2.0, k=3, current="critical") == "warning"
    assert target_level([2.5, 1.5, 1.5], "gt", 1.0, 2.0, k=3, current="critical") == "critical"
    assert target_level([0.5, 0.5, 0.5], "gt", 1.0, 2.0, k=3, current="warning") is None
    assert target_level([0.5, 1.5, 0.5], "gt", 1.0, 2.0, k=3, current="warning") == "warning"


def test_less_than_comparator():
    """R7: 'lt' rules (battery) alarm when the value drops below the threshold."""
    assert target_level([15, 14, 13], "lt", 20, 10, k=3, current=None) == "warning"
    assert target_level([9, 8, 7], "lt", 20, 10, k=3, current="warning") == "critical"


# ------------------------------------------------------------------ through the ingest API


def send_tilts(client, key, dev_eui, t0, tilts, start_minute):
    """Send readings whose tilt change from the 5° baseline equals each value in `tilts`."""
    batch = [
        make_reading(dev_eui, t0 + timedelta(minutes=start_minute + i), angle_x=5.0 + t)
        for i, t in enumerate(tilts)
    ]
    assert ingest(client, key, batch).status_code in (200, 201)
    return start_minute + len(tilts)


def active_alerts(db, node_id):
    db.expire_all()
    return db.scalars(
        select(Alert).where(Alert.node_id == node_id, Alert.status.in_(("open", "acknowledged")))
    ).all()


def test_tilt_alert_warning_then_critical_then_resolves(client, auth, db, t0):
    """R5 + R7: tilt rule opens warning, escalates to critical, then auto-resolves."""
    node, key = register_node(client, auth, rules=[TILT_RULE])
    m = send_tilts(client, key, node["dev_eui"], t0, [0.0] * 10, 0)  # baseline at 5°

    m = send_tilts(client, key, node["dev_eui"], t0, [1.5, 1.5], m)
    assert active_alerts(db, node["id"]) == []  # only 2 breaches so far

    m = send_tilts(client, key, node["dev_eui"], t0, [1.5], m)
    [warning] = active_alerts(db, node["id"])
    assert warning.level == "warning"
    assert warning.opened_at == t0 + timedelta(minutes=m - 1)  # uses the reading's time

    m = send_tilts(client, key, node["dev_eui"], t0, [1.5, 1.5], m)
    assert len(active_alerts(db, node["id"])) == 1  # continued breaches: no duplicates

    m = send_tilts(client, key, node["dev_eui"], t0, [2.5, 2.5, 2.5], m)
    [critical] = active_alerts(db, node["id"])
    assert critical.level == "critical"
    db.refresh(warning)
    assert warning.status == "resolved" and warning.resolution_note == "Escalated to critical"

    m = send_tilts(client, key, node["dev_eui"], t0, [0.1, 0.1, 0.1], m)
    assert active_alerts(db, node["id"]) == []
    db.refresh(critical)
    assert critical.status == "resolved"

    status = client.get(f"/api/nodes/{node['id']}", headers=auth).json()["status"]
    assert status in ("ok", "offline")  # offline only because t0 is in the past


def test_flagged_readings_are_ignored_by_alerts(client, auth, db, t0):
    """R8 + R7: spike readings neither count as breaches nor break a run of breaches."""
    node, key = register_node(client, auth, rules=[TILT_RULE])
    m = send_tilts(client, key, node["dev_eui"], t0, [0.0] * 10, 0)
    dev = node["dev_eui"]
    batch = [
        make_reading(dev, t0 + timedelta(minutes=m), angle_x=6.5),
        make_reading(dev, t0 + timedelta(minutes=m + 1), angle_x=99.0),  # out of range -> flagged
        make_reading(dev, t0 + timedelta(minutes=m + 2), angle_x=6.5),
    ]
    ingest(client, key, batch)
    assert active_alerts(db, node["id"]) == []  # only 2 valid breaches
    ingest(client, key, make_reading(dev, t0 + timedelta(minutes=m + 3), angle_x=6.5))
    assert [a.level for a in active_alerts(db, node["id"])] == ["warning"]


def test_battery_lt_rule(client, auth, db, t0):
    """R7: battery uses the 'less than' comparator: warning below 20 %, critical below 10 %."""
    node, key = register_node(client, auth, rules=[BATTERY_RULE])
    dev = node["dev_eui"]
    ingest(client, key, [make_reading(dev, t0 + timedelta(minutes=i), battery_pct=15.0) for i in range(3)])
    assert [a.level for a in active_alerts(db, node["id"])] == ["warning"]
    ingest(client, key, [make_reading(dev, t0 + timedelta(minutes=3 + i), battery_pct=8.0) for i in range(3)])
    assert [a.level for a in active_alerts(db, node["id"])] == ["critical"]


def test_disabled_rule_does_not_fire(client, auth, db, t0):
    node, key = register_node(client, auth, rules=[{**BATTERY_RULE, "enabled": False}])
    ingest(client, key, [make_reading(node["dev_eui"], t0 + timedelta(minutes=i), battery_pct=5.0) for i in range(5)])
    assert active_alerts(db, node["id"]) == []


def test_offline_alert_opens_and_closes(client, auth, db, t0):
    """R7/R9: a node silent for > 3 x interval gets an offline alert, closed when data resumes."""
    node, key = register_node(client, auth, interval=60)
    ingest(client, key, make_reading(node["dev_eui"], t0))
    now = t0 + timedelta(minutes=10)

    assert check_offline_nodes(db, now) == 1
    [offline] = active_alerts(db, node["id"])
    assert offline.parameter == "offline" and offline.level == "warning"
    assert offline.opened_at == t0 + timedelta(minutes=3)
    assert check_offline_nodes(db, now) == 0  # no duplicate

    ingest(client, key, make_reading(node["dev_eui"], t0 + timedelta(minutes=11)))
    assert active_alerts(db, node["id"]) == []
    db.refresh(offline)
    assert offline.status == "resolved" and offline.resolved_at == t0 + timedelta(minutes=11)


def test_node_not_offline_within_threshold(client, auth, db, t0):
    node, key = register_node(client, auth, interval=60)
    ingest(client, key, make_reading(node["dev_eui"], t0))
    assert check_offline_nodes(db, t0 + timedelta(minutes=2)) == 0


def test_gap_in_uploaded_history_is_recorded(client, auth, db, t0):
    """R8/R9: a long gap in (backfilled) data is recorded as a resolved offline alert."""
    node, key = register_node(client, auth, interval=60)
    dev = node["dev_eui"]
    ingest(client, key, [make_reading(dev, t0), make_reading(dev, t0 + timedelta(minutes=30))])
    db.expire_all()
    [gap] = db.scalars(select(Alert).where(Alert.parameter == "offline")).all()
    assert gap.status == "resolved"
    assert gap.opened_at == t0 + timedelta(minutes=3)
    assert gap.resolved_at == t0 + timedelta(minutes=30)


def test_premature_offline_alert_is_removed_when_late_data_arrives(client, auth, db, t0):
    """An offline alert raised while data was still being uploaded is removed, not left in history."""
    node, key = register_node(client, auth, interval=60)
    dev = node["dev_eui"]
    ingest(client, key, make_reading(dev, t0))
    check_offline_nodes(db, t0 + timedelta(minutes=10))  # checker runs before the rest arrives
    ingest(client, key, [make_reading(dev, t0 + timedelta(minutes=i)) for i in range(1, 12)])
    db.expire_all()
    assert db.scalars(select(Alert).where(Alert.parameter == "offline")).all() == []


def test_inactive_nodes_are_not_checked_for_offline(client, auth, db, t0):
    node, key = register_node(client, auth)
    ingest(client, key, make_reading(node["dev_eui"], t0))
    db.get(Node, node["id"]).is_active = False
    db.commit()
    assert check_offline_nodes(db, t0 + timedelta(hours=1)) == 0


def test_acknowledge_keeps_alert_active(client, auth, db, t0):
    """Acknowledging stops an alert showing as new but keeps it until resolved."""
    node, key = register_node(client, auth, rules=[BATTERY_RULE])
    ingest(client, key, [make_reading(node["dev_eui"], t0 + timedelta(minutes=i), battery_pct=15.0) for i in range(3)])
    [alert] = active_alerts(db, node["id"])
    r = client.post(f"/api/alerts/{alert.id}/acknowledge", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"
    assert client.post(f"/api/alerts/{alert.id}/acknowledge", headers=auth).status_code == 409
    summary = client.get("/api/dashboard/summary", headers=auth).json()
    assert summary["counts"]["alerts_active"] == 1 and summary["counts"]["alerts_new"] == 0
