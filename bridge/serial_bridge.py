"""Point-to-point LoRa serial bridge — STUB for later (handoff.md section 12).

For a REYAX RYLR998 (or similar) LoRa receiver plugged into this PC's serial
port. It reads each received packet, turns it into the JSON ingest format and
POSTs it to /api/ingest — exactly what the simulator does today.

NOT INSTALLED YET: this needs the `pyserial` library, which must be approved
by the owner before adding it (`pip install pyserial`). Until then, only the
packet parsing below is usable (and testable).

RYLR998 output lines look like:   +RCV=<address>,<length>,<data>,<RSSI>,<SNR>
We assume the node puts comma-separated key=value pairs in <data>, e.g.
    eui=70b3d57ed0000007;ax=1.92;ay=-0.41;bat=87
The exact on-air format is decided when the firmware is written; only
FIELD_MAP and parse_rcv_line() should need to change.

Usage (later):
    py -3.13 serial_bridge.py --port COM5 --api-key <node key>
"""

import argparse
import json
import urllib.request
from datetime import datetime, timezone

API_URL = "http://127.0.0.1:8000/api/ingest"

# Short on-air names -> ingest field names (short names keep LoRa packets small).
FIELD_MAP = {
    "eui": "dev_eui", "seq": "seq",
    "lat": "lat", "lon": "lon",
    "ax": "angle_x", "ay": "angle_y", "az": "angle_z",
    "gx": "acc_x", "gy": "acc_y", "gz": "acc_z",
    "rx": "gyro_x", "ry": "gyro_y", "rz": "gyro_z",
    "mx": "mag_x", "my": "mag_y", "mz": "mag_z",
    "t": "temperature", "h": "humidity", "bat": "battery_pct", "v": "battery_v",
}


def parse_rcv_line(line: str) -> dict | None:
    """Turn one '+RCV=...' line into an ingest payload dict (None if it isn't a packet)."""
    line = line.strip()
    if not line.startswith("+RCV="):
        return None
    # Split from both ends: the data part may itself contain commas.
    _address, _length, rest = line[len("+RCV="):].split(",", 2)
    data, rssi, snr = rest.rsplit(",", 2)
    reading: dict = {"rssi": float(rssi), "snr": float(snr), "ts": datetime.now(timezone.utc).isoformat()}
    for pair in data.split(";"):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        field = FIELD_MAP.get(key.strip())
        if field == "dev_eui":
            reading[field] = value.strip()
        elif field == "seq":
            reading[field] = int(value)
        elif field:
            reading[field] = float(value)
    return reading if "dev_eui" in reading else None


def post(reading: dict, api_key: str) -> None:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(reading).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.status, response.read().decode())


def main() -> None:
    parser = argparse.ArgumentParser(description="LoRa serial bridge (stub)")
    parser.add_argument("--port", required=True, help="e.g. COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args()

    try:
        import serial  # pyserial — not installed until approved
    except ImportError:
        raise SystemExit("pyserial is not installed. Ask the owner, then: pip install pyserial")

    with serial.Serial(args.port, args.baud, timeout=1) as port:
        print(f"Listening on {args.port}… (Ctrl+C to stop)")
        while True:
            line = port.readline().decode(errors="replace")
            reading = parse_rcv_line(line)
            if reading:
                post(reading, args.api_key)


if __name__ == "__main__":
    main()
