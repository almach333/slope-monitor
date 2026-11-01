"""Ingest endpoint (handoff section 6): authentication, validation, duplicates, flags."""

from datetime import timedelta

from sqlalchemy import func, select

from app.models import Node, Reading
from tests.conftest import ingest, make_reading, register_node


def count_readings(db) -> int:
    return db.scalar(select(func.count()).select_from(Reading))


def test_valid_payload_is_stored(client, auth, db, t0):
    """R3: a valid reading is stored and returned by the readings API."""
    node, key = register_node(client, auth)
    r = ingest(client, key, make_reading(node["dev_eui"], t0))
    assert r.status_code == 201
    assert r.json()["stored"] == 1
    assert count_readings(db) == 1
    page = client.get(
        "/api/readings", params={"node_ids": node["id"], "from": (t0 - timedelta(minutes=1)).isoformat()}, headers=auth
    )
    assert page.json()["total"] == 1


def test_bad_or_missing_api_key_is_401(client, auth, db, t0):
    """Only devices with a valid key can send data."""
    node, _ = register_node(client, auth)
    assert ingest(client, "wrong-key", make_reading(node["dev_eui"], t0)).status_code == 401
    assert client.post("/api/ingest", json=make_reading(node["dev_eui"], t0)).status_code == 401
    assert count_readings(db) == 0


def test_key_must_match_dev_eui(client, auth, t0):
    """A node's key can't be used to send data as another node."""
    _, key_a = register_node(client, auth, dev_eui="70b3d57ed00000a1")
    register_node(client, auth, dev_eui="70b3d57ed00000b2")
    assert ingest(client, key_a, make_reading("70b3d57ed00000b2", t0)).status_code == 401


def test_api_key_is_stored_hashed(client, auth, db):
    """Device API keys are stored hashed; the plain key is only returned once."""
    node, key = register_node(client, auth)
    stored = db.get(Node, node["id"]).api_key_hash
    assert key not in stored and len(stored) == 64


def test_duplicate_timestamp_is_not_stored_twice(client, auth, db, t0):
    """A second reading with the same node and timestamp returns 200 duplicate=true."""
    node, key = register_node(client, auth)
    assert ingest(client, key, make_reading(node["dev_eui"], t0)).status_code == 201
    r = ingest(client, key, make_reading(node["dev_eui"], t0))
    assert r.status_code == 200
    assert r.json()["duplicate"] is True
    assert count_readings(db) == 1


def test_out_of_range_value_is_stored_with_a_flag(client, auth, db, t0):
    """R8: out-of-range values are flagged but still stored, never silently dropped."""
    node, key = register_node(client, auth)
    r = ingest(client, key, make_reading(node["dev_eui"], t0, angle_x=99.0))
    assert r.status_code == 201
    assert r.json()["flagged"] == 1
    reading = db.scalars(select(Reading)).one()
    assert reading.angle_x == 99.0
    assert "angle_x_out_of_range" in reading.quality_flags


def test_batch_of_readings(client, auth, db, t0):
    """A list of readings is stored in one request (used by backfill and bridges)."""
    node, key = register_node(client, auth)
    batch = [make_reading(node["dev_eui"], t0 + timedelta(minutes=i)) for i in range(20)]
    r = ingest(client, key, batch)
    assert r.status_code == 201
    assert r.json()["stored"] == 20
    assert count_readings(db) == 20


def test_missing_optional_fields_are_allowed(client, auth, db, t0):
    """Only dev_eui is required; a reading with just battery is fine."""
    node, key = register_node(client, auth)
    r = ingest(client, key, {"dev_eui": node["dev_eui"], "ts": t0.isoformat(), "battery_pct": 50})
    assert r.status_code == 201


def test_wrong_type_is_rejected(client, auth, t0):
    """Types are validated: text where a number is expected gets 422."""
    node, key = register_node(client, auth)
    r = ingest(client, key, make_reading(node["dev_eui"], t0, temperature="hot"))
    assert r.status_code == 422


def test_future_timestamp_is_rejected(client, auth, t0):
    node, key = register_node(client, auth)
    r = ingest(client, key, make_reading(node["dev_eui"], t0 + timedelta(days=1)))
    assert r.status_code == 422


def test_deactivated_node_is_refused(client, auth, t0):
    node, key = register_node(client, auth)
    client.patch(f"/api/nodes/{node['id']}", json={"is_active": False}, headers=auth)
    assert ingest(client, key, make_reading(node["dev_eui"], t0)).status_code == 403


def test_baseline_is_set_automatically_from_first_readings(client, auth, t0):
    """Tilt baseline = median of the first 10 valid readings, so tilt alerts work without manual setup."""
    node, key = register_node(client, auth)
    ingest(client, key, [make_reading(node["dev_eui"], t0 + timedelta(minutes=i), angle_x=5.0) for i in range(10)])
    detail = client.get(f"/api/nodes/{node['id']}", headers=auth).json()
    assert detail["baseline_angle_x"] == 5.0
    assert detail["latest"]["values"]["tilt_change_total"] == 0.0
