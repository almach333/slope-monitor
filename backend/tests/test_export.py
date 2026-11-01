"""R10 (proposed): export historical data as CSV."""

import csv
import io
from datetime import timedelta

from app.derived import ALL_FIELDS
from tests.conftest import ingest, make_reading, register_node


def test_csv_has_headers_and_matches_readings_in_range(client, auth, t0):
    """R10: the CSV has a header row and exactly the readings inside the requested range."""
    node, key = register_node(client, auth)
    ingest(client, key, [make_reading(node["dev_eui"], t0 + timedelta(minutes=i)) for i in range(10)])

    r = client.get(
        "/api/readings/export",
        params={
            "node_ids": node["id"],
            "from": (t0 + timedelta(minutes=2)).isoformat(),
            "to": (t0 + timedelta(minutes=6)).isoformat(),
        },
        headers=auth,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(r.text)))
    header, data = rows[0], rows[1:]
    assert header[:5] == ["node", "dev_eui", "ts", "received_at", "seq"]
    assert set(ALL_FIELDS) <= set(header)
    assert len(data) == 5  # minutes 2, 3, 4, 5, 6
    assert all(row[1] == node["dev_eui"] for row in data)


def test_export_requires_login(client):
    """R1/R10: exports are only available to signed-in users."""
    assert client.get("/api/readings/export").status_code == 401
