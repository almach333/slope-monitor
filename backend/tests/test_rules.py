"""R6: the safe limit can be set and changed, with justification (and an audit trail)."""

from datetime import timedelta

from tests.conftest import ingest, make_reading, register_node

RULE = {
    "parameter": "acc_magnitude",
    "comparator": "gt",
    "warning_threshold": 1.2,
    "critical_threshold": 1.5,
    "consecutive_readings": 3,
    "justification": "Placeholder from handoff defaults",
}


def test_create_rule_without_justification_is_rejected(client, auth):
    """R6: creating a rule without a justification is rejected."""
    node, _ = register_node(client, auth)
    no_just = {k: v for k, v in RULE.items() if k != "justification"}
    assert client.post(f"/api/nodes/{node['id']}/alert-rules", json=no_just, headers=auth).status_code == 422
    blank = {**RULE, "justification": "    "}
    assert client.post(f"/api/nodes/{node['id']}/alert-rules", json=blank, headers=auth).status_code == 422


def test_register_node_with_rule_missing_justification_is_rejected(client, auth):
    """R6: the New Device page can't save rules without a justification either."""
    body = {"name": "X", "dev_eui": "70b3d57ed00000cc", "rules": [{**RULE, "justification": ""}]}
    assert client.post("/api/nodes", json=body, headers=auth).status_code == 422


def test_update_rule_without_justification_is_rejected(client, auth):
    """R6: updating a rule without a justification is rejected."""
    node, _ = register_node(client, auth, rules=[RULE])
    rule_id = client.get(f"/api/nodes/{node['id']}/alert-rules", headers=auth).json()[0]["id"]
    r = client.patch(f"/api/nodes/{node['id']}/alert-rules/{rule_id}", json={"warning_threshold": 1.3}, headers=auth)
    assert r.status_code == 422


def test_rule_change_is_recorded_with_who_and_why(client, auth, user):
    """R6: every change stores updated_by/updated_at and a history entry with old and new values."""
    node, _ = register_node(client, auth, rules=[RULE])
    rule_id = client.get(f"/api/nodes/{node['id']}/alert-rules", headers=auth).json()[0]["id"]
    r = client.patch(
        f"/api/nodes/{node['id']}/alert-rules/{rule_id}",
        json={"warning_threshold": 1.3, "critical_threshold": 1.6, "justification": "Site TARP rev B, section 4.2"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["warning_threshold"] == 1.3
    assert r.json()["updated_by"] == user.id

    history = client.get(f"/api/nodes/{node['id']}/alert-rules/history", headers=auth).json()
    assert [h["action"] for h in history] == ["updated", "created"]
    latest = history[0]
    assert latest["justification"] == "Site TARP rev B, section 4.2"
    assert latest["old_values"]["warning_threshold"] == 1.2
    assert latest["new_values"]["warning_threshold"] == 1.3
    assert latest["changed_by_name"] == user.name


def test_critical_must_be_beyond_warning(client, auth):
    """R7: for 'gt' rules critical must be above warning (and below it for 'lt')."""
    node, _ = register_node(client, auth)
    bad = {**RULE, "warning_threshold": 1.5, "critical_threshold": 1.2}
    assert client.post(f"/api/nodes/{node['id']}/alert-rules", json=bad, headers=auth).status_code == 422
    bad_lt = {**RULE, "parameter": "battery_pct", "comparator": "lt", "warning_threshold": 10, "critical_threshold": 20}
    assert client.post(f"/api/nodes/{node['id']}/alert-rules", json=bad_lt, headers=auth).status_code == 422


def test_delete_rule_requires_justification_and_is_logged(client, auth):
    node, _ = register_node(client, auth, rules=[RULE])
    rule_id = client.get(f"/api/nodes/{node['id']}/alert-rules", headers=auth).json()[0]["id"]
    assert client.delete(f"/api/nodes/{node['id']}/alert-rules/{rule_id}", headers=auth).status_code == 422
    r = client.delete(
        f"/api/nodes/{node['id']}/alert-rules/{rule_id}", params={"justification": "Sensor removed from site"}, headers=auth
    )
    assert r.status_code == 204
    history = client.get(f"/api/nodes/{node['id']}/alert-rules/history", headers=auth).json()
    assert history[0]["action"] == "deleted"


def test_slope_angle_rule_waits_for_baseline_then_uses_offsets(client, auth, t0):
    """R5/R6: the slope-angle rule is 'pending baseline' until a baseline exists, then = baseline + offsets."""
    rule = {
        "parameter": "slope_angle",
        "comparator": "gt",
        "warning_offset": 1.0,
        "critical_offset": 2.0,
        "justification": "Placeholder: baseline +1/+2 degrees",
    }
    node, key = register_node(client, auth, rules=[rule])
    [pending] = client.get(f"/api/nodes/{node['id']}/alert-rules", headers=auth).json()
    assert pending["pending_baseline"] is True and pending["warning_threshold"] is None

    ingest(client, key, [make_reading(node["dev_eui"], t0 + timedelta(minutes=i), angle_x=5.0) for i in range(10)])
    [ready] = client.get(f"/api/nodes/{node['id']}/alert-rules", headers=auth).json()
    assert ready["pending_baseline"] is False
    assert ready["warning_threshold"] == round(5.0 + 1.0, 4)
    assert ready["critical_threshold"] == round(5.0 + 2.0, 4)


def test_manual_baseline_updates_slope_thresholds(client, auth, t0):
    """'Set baseline now' re-centres tilt and recalculates baseline-relative thresholds."""
    rule = {"parameter": "slope_angle", "comparator": "gt", "warning_offset": 1.0, "critical_offset": 2.0,
            "justification": "Placeholder: baseline +1/+2 degrees"}
    node, key = register_node(client, auth, rules=[rule])
    ingest(client, key, [make_reading(node["dev_eui"], t0 + timedelta(minutes=i), angle_x=5.0) for i in range(10)])
    ingest(client, key, [make_reading(node["dev_eui"], t0 + timedelta(minutes=10 + i), angle_x=8.0) for i in range(10)])
    r = client.post(f"/api/nodes/{node['id']}/baseline", json={"readings": 10}, headers=auth)
    assert r.status_code == 200
    assert r.json()["node"]["baseline_angle_x"] == 8.0
    assert r.json()["updated_rules"][0]["warning_threshold"] == 9.0
    detail = client.get(f"/api/nodes/{node['id']}", headers=auth).json()
    assert detail["latest"]["values"]["tilt_change_total"] == 0.0


def test_defaults_endpoint_lists_required_parameters(client, auth):
    """User stories: battery, acceleration and slope angle (plus tilt) are offered by default."""
    defaults = client.get("/api/alert-rules/defaults", headers=auth).json()
    params = {r["parameter"] for r in defaults["rules"]}
    assert {"battery_pct", "acc_magnitude", "slope_angle", "tilt_change_total"} <= params
    assert "placeholder" in defaults["note"].lower()
