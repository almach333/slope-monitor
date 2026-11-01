"""R3: historical data for charts: downsampling, gaps and flagged-point hiding."""

from datetime import timedelta

from tests.conftest import ingest, make_reading, register_node


def test_downsampling_caps_points(client, auth, t0):
    """R3: long ranges are averaged so charts get at most max_points points."""
    node, key = register_node(client, auth)
    readings = [make_reading(node["dev_eui"], t0 + timedelta(seconds=10 * i)) for i in range(600)]
    ingest(client, key, readings)
    r = client.get(
        f"/api/nodes/{node['id']}/readings",
        params={"from": t0.isoformat(), "to": (t0 + timedelta(hours=2)).isoformat(), "max_points": 50},
        headers=auth,
    )
    body = r.json()
    assert r.status_code == 200
    assert body["bucket_s"] > 0
    assert len([p for p in body["points"] if not p.get("gap")]) <= 50


def test_gaps_are_marked_with_null_points(client, auth, t0):
    """R8: missing data shows as a gap (a null point), not a line across it."""
    node, key = register_node(client, auth, interval=60)
    dev = node["dev_eui"]
    ingest(client, key, [make_reading(dev, t0 + timedelta(minutes=i)) for i in range(5)])
    ingest(client, key, [make_reading(dev, t0 + timedelta(minutes=40 + i)) for i in range(5)])
    body = client.get(
        f"/api/nodes/{node['id']}/readings",
        params={"from": t0.isoformat(), "to": (t0 + timedelta(hours=1)).isoformat(), "fields": "battery_pct"},
        headers=auth,
    ).json()
    gaps = [p for p in body["points"] if p.get("gap")]
    assert len(gaps) == 1 and gaps[0]["battery_pct"] is None


def test_flagged_values_hidden_unless_requested(client, auth, t0):
    """R8: flagged values are hidden on charts by default, shown with include_flagged."""
    node, key = register_node(client, auth)
    ingest(client, key, make_reading(node["dev_eui"], t0, angle_x=99.0))
    params = {"from": (t0 - timedelta(minutes=1)).isoformat(), "fields": "angle_x,battery_pct"}
    hidden = client.get(f"/api/nodes/{node['id']}/readings", params=params, headers=auth).json()["points"][0]
    assert hidden["angle_x"] is None and hidden["battery_pct"] == 90.0  # only the bad field is hidden
    shown = client.get(
        f"/api/nodes/{node['id']}/readings", params={**params, "include_flagged": True}, headers=auth
    ).json()["points"][0]
    assert shown["angle_x"] == 99.0 and shown["flagged"] is True


def test_multi_node_series(client, auth, t0):
    """R2/R3: one field for several nodes at once (Results comparison chart)."""
    a, key_a = register_node(client, auth, dev_eui="70b3d57ed00000a1")
    b, key_b = register_node(client, auth, dev_eui="70b3d57ed00000b2")
    ingest(client, key_a, make_reading(a["dev_eui"], t0))
    ingest(client, key_b, make_reading(b["dev_eui"], t0))
    body = client.get(
        "/api/readings/series",
        params={"field": "battery_pct", "node_ids": f"{a['id']},{b['id']}", "from": (t0 - timedelta(minutes=1)).isoformat()},
        headers=auth,
    ).json()
    assert [len(s["points"]) for s in body["series"]] == [1, 1]


def test_unknown_field_is_rejected(client, auth):
    node, _ = register_node(client, auth)
    assert client.get(f"/api/nodes/{node['id']}/readings", params={"fields": "nope"}, headers=auth).status_code == 422


def test_dashboard_summary_counts(client, auth, t0):
    """R2: the dashboard counts every node and reports each node's status."""
    register_node(client, auth, dev_eui="70b3d57ed00000a1")
    register_node(client, auth, dev_eui="70b3d57ed00000b2")
    body = client.get("/api/dashboard/summary", headers=auth).json()
    assert body["counts"]["nodes"] == 2
    assert body["counts"]["offline"] == 2  # never sent data
    assert {n["status"] for n in body["nodes"]} == {"offline"}
