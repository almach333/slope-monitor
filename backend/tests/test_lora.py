"""Section 12 (later): real LoRaWAN data arrives through the same ingest function."""

from tests.conftest import register_node


def test_ttn_webhook_uplink_is_ingested(client, auth, t0):
    """A The Things Stack uplink is mapped to the ingest schema and stored like any reading."""
    node, key = register_node(client, auth)
    uplink = {
        "end_device_ids": {"device_id": "n7", "dev_eui": node["dev_eui"].upper()},
        "uplink_message": {
            "f_cnt": 42,
            "received_at": t0.isoformat(),
            "decoded_payload": {"angle_x": 5.0, "angle_y": 0.1, "battery_pct": 77.0, "temperature": 21.5},
            "rx_metadata": [{"rssi": -101, "snr": 3.0}, {"rssi": -95, "snr": 6.0}],
        },
    }
    r = client.post("/api/ingest/ttn", json=uplink, headers={"X-API-Key": key})
    assert r.status_code == 201, r.text
    latest = client.get(f"/api/nodes/{node['id']}", headers=auth).json()["latest"]
    assert latest["seq"] == 42
    assert latest["values"]["battery_pct"] == 77.0
    assert latest["values"]["rssi"] == -95  # strongest gateway


def test_ttn_webhook_needs_the_node_key(client, auth, t0):
    node, _ = register_node(client, auth)
    uplink = {"end_device_ids": {"dev_eui": node["dev_eui"]}, "uplink_message": {"decoded_payload": {}}}
    assert client.post("/api/ingest/ttn", json=uplink, headers={"X-API-Key": "nope"}).status_code == 401
