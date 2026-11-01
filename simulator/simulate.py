"""Slope Monitor data simulator.

Posts realistic sensor readings for 6 demo nodes to the backend's
/api/ingest endpoint — the same endpoint real LoRa data will use later.
Uses only the Python standard library, so no extra installs are needed.

Commands (run from the simulator/ folder, with the backend running):
    py -3.13 simulate.py setup                         # register the 6 nodes (done automatically)
    py -3.13 simulate.py backfill --days 7 --interval 60  # generate history quickly
    py -3.13 simulate.py live --interval 10            # send live readings until Ctrl+C

Node API keys and the scenario timeline are saved in simulator/keys.json.
To start over: `python -m scripts.seed --reset` in backend/, then delete keys.json.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import scenarios

STATE_FILE = Path(__file__).resolve().parent / "keys.json"
BATCH_SIZE = 500


# ---------------------------------------------------------------- HTTP helpers


def http(method: str, path: str, body=None, headers: dict | None = None, form: dict | None = None):
    """Send a request to the API and return (status code, parsed JSON)."""
    url = config.API_URL.rstrip("/") + path
    headers = dict(headers or {})
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode(errors="replace")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach the API at {config.API_URL} ({e.reason}). Is the backend running?")


def login() -> dict:
    status, body = http(
        "POST", "/api/auth/token", form={"username": config.LOGIN_EMAIL, "password": config.LOGIN_PASSWORD}
    )
    if status != 200:
        sys.exit(f"Login failed ({status}): {body}. Did you run `python -m scripts.seed` in backend/?")
    return {"Authorization": f"Bearer {body['access_token']}"}


# ---------------------------------------------------------------- state (keys.json)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"nodes": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------- commands


def setup(state: dict) -> dict:
    """Register any demo node that isn't in keys.json yet (with the default alert rules)."""
    missing = [n for n in config.NODES if n["dev_eui"] not in state["nodes"]]
    if not missing:
        return state
    auth = login()
    status, defaults = http("GET", "/api/alert-rules/defaults", headers=auth)
    if status != 200:
        sys.exit(f"Could not load default rules ({status}): {defaults}")
    _, existing = http("GET", "/api/nodes", headers=auth)
    existing_by_eui = {n["dev_eui"]: n for n in existing or []}

    for node in missing:
        lat, lon = scenarios.offset_position(node["east_m"], node["north_m"])
        if node["dev_eui"] in existing_by_eui:
            # Registered before but the key was lost: issue a new key.
            node_id = existing_by_eui[node["dev_eui"]]["id"]
            status, body = http("POST", f"/api/nodes/{node_id}/rotate-key", headers=auth)
            if status != 200:
                sys.exit(f"Could not rotate key for {node['name']} ({status}): {body}")
            api_key = body["api_key"]
            print(f"  {node['name']}: already registered, issued a new API key")
        else:
            status, body = http(
                "POST",
                "/api/nodes",
                headers=auth,
                body={
                    "name": node["name"],
                    "dev_eui": node["dev_eui"],
                    "description": f"Simulated node ({node['scenario']} scenario). Placeholder site, not a real mine.",
                    "ref_lat": round(lat, 7),
                    "ref_lon": round(lon, 7),
                    "expected_interval_s": config.EXPECTED_INTERVAL_S,
                    "rules": defaults["rules"],
                },
            )
            if status != 201:
                sys.exit(f"Could not register {node['name']} ({status}): {body}")
            node_id, api_key = body["node"]["id"], body["api_key"]
            print(f"  {node['name']}: registered")
        state["nodes"][node["dev_eui"]] = {"id": node_id, "api_key": api_key, "seq": 0, "last_ts": None}
    save_state(state)
    print(f"Saved node keys to {STATE_FILE.name}")
    return state


def post_readings(node_state: dict, readings: list[dict]) -> dict:
    status, body = http("POST", "/api/ingest", body=readings, headers={"X-API-Key": node_state["api_key"]})
    if status not in (200, 201):
        sys.exit(f"Ingest failed ({status}): {body}")
    return body


def send_range(state: dict, node: dict, start: datetime, end: datetime, interval: int, live: bool) -> dict:
    """Generate and post readings for one node from start to end. Returns totals."""
    ns = state["nodes"][node["dev_eui"]]
    t0, days, seed = parse_ts(state["t0"]), state["days"], state["seed"]
    totals = {"stored": 0, "duplicates": 0, "flagged": 0, "dropped": 0}
    batch: list[dict] = []
    for ts in scenarios.timeline(start, end, interval):
        ns["seq"] += 1  # the device counts every transmission, even ones we never receive
        reading = scenarios.sample(node, ts, t0, days, seed, live)
        if reading is None:
            totals["dropped"] += 1
            continue
        reading["seq"] = ns["seq"]
        batch.append(reading)
        if len(batch) >= BATCH_SIZE:
            result = post_readings(ns, batch)
            for k in ("stored", "duplicates", "flagged"):
                totals[k] += result[k]
            batch = []
    if batch:
        result = post_readings(ns, batch)
        for k in ("stored", "duplicates", "flagged"):
            totals[k] += result[k]
    ns["last_ts"] = end.isoformat()
    return totals


def ensure_timeline(state: dict, days: float, seed: int, now: datetime) -> None:
    """Fix the scenario start time (t0). Saved so backfill and live line up."""
    if "t0" not in state:
        state["t0"] = (now - timedelta(days=days)).isoformat()
        state["days"] = days
        state["seed"] = seed


def backfill(args) -> None:
    state = setup(load_state())
    if "t0" in state and any(n.get("last_ts") for n in state["nodes"].values()):
        sys.exit(
            "History was already generated. To start over: run `python -m scripts.seed --reset` "
            "in backend/ and delete simulator/keys.json."
        )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ensure_timeline(state, args.days, args.seed, now)
    t0 = parse_ts(state["t0"])
    print(f"Backfilling {args.days} days at {args.interval} s intervals for {len(config.NODES)} nodes...")
    for node in config.NODES:
        started = time.monotonic()
        totals = send_range(state, node, t0, now, args.interval, live=False)
        save_state(state)
        print(
            f"  {node['name']:<16} stored {totals['stored']:>6}  flagged {totals['flagged']:>4}  "
            f"dropped {totals['dropped']:>4}  ({time.monotonic() - started:.1f} s)"
        )
    print("Done. Now start live mode:  py -3.13 simulate.py live --interval 10")


def live(args) -> None:
    state = setup(load_state())
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ensure_timeline(state, args.days, args.seed, now)

    # Catch up: fill any gap since the simulator last ran, so the nodes look
    # like they kept running. (The backend will still have recorded them as
    # offline if the gap was long.)
    for node in config.NODES:
        ns = state["nodes"][node["dev_eui"]]
        if ns.get("last_ts"):
            last = parse_ts(ns["last_ts"])
            if now - last > timedelta(seconds=2 * config.EXPECTED_INTERVAL_S):
                totals = send_range(
                    state, node, last + timedelta(seconds=config.EXPECTED_INTERVAL_S), now,
                    config.EXPECTED_INTERVAL_S, live=False,
                )
                print(f"  {node['name']}: caught up {totals['stored']} readings since {last:%Y-%m-%d %H:%M} UTC")
    save_state(state)

    print(f"Live mode: one reading per node every {args.interval} s. Press Ctrl+C to stop.")
    print(f"N6 goes silent for {config.N6_OUTAGE_LENGTH_MIN} min every {config.N6_OUTAGE_EVERY_MIN} min.")
    try:
        while True:
            tick = datetime.now(timezone.utc).replace(microsecond=0)
            sent = []
            for node in config.NODES:
                ns = state["nodes"][node["dev_eui"]]
                totals = send_range(state, node, tick, tick, args.interval, live=True)
                sent.append(node["key"] if totals["stored"] else f"({node['key']})")
            save_state(state)
            print(f"{tick:%H:%M:%S} UTC  sent: {' '.join(sent)}   (brackets = not received)")
            time.sleep(max(0.0, args.interval - (datetime.now(timezone.utc) - tick).total_seconds()))
    except KeyboardInterrupt:
        save_state(state)
        print("\nStopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Slope Monitor simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="register the demo nodes and save their API keys")

    p_back = sub.add_parser("backfill", help="generate history quickly")
    p_back.add_argument("--days", type=float, default=7.0)
    p_back.add_argument("--interval", type=int, default=60, help="seconds between readings")
    p_back.add_argument("--seed", type=int, default=42, help="random seed (same seed = same data)")

    p_live = sub.add_parser("live", help="send live readings until stopped")
    p_live.add_argument("--interval", type=int, default=10, help="seconds between readings")
    p_live.add_argument("--days", type=float, default=7.0, help="scenario length if no backfill was run")
    p_live.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()
    if args.command == "setup":
        setup(load_state())
    elif args.command == "backfill":
        backfill(args)
    else:
        live(args)


if __name__ == "__main__":
    main()
