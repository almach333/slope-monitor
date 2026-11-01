"""Simulator settings: API address, demo login, site centre and the 6 demo nodes.

The site centre is a PLACEHOLDER (University of Queensland, St Lucia — the
coordinates from the handoff's example payload). It is NOT a real mine.
Change SITE_CENTRE to move the whole demo site.
"""

import os

# Use 127.0.0.1 rather than "localhost": on Windows, "localhost" tries IPv6
# first and every request waits ~2 s before falling back to IPv4.
API_URL = os.environ.get("SLOPE_API_URL", "http://127.0.0.1:8000")

# Must match backend/scripts/seed.py (the demo admin it creates).
LOGIN_EMAIL = os.environ.get("SLOPE_EMAIL", "admin@example.com")
LOGIN_PASSWORD = os.environ.get("SLOPE_PASSWORD", "slope-demo-2026")

# Placeholder site centre (lat, lon) — not a real mine.
SITE_CENTRE = (-27.4975, 153.0137)

# How often each node is expected to report, in seconds (registered with the API).
EXPECTED_INTERVAL_S = 60

# N6 live-mode outage: silent for OUTAGE_LENGTH_MIN minutes every OUTAGE_EVERY_MIN minutes.
N6_OUTAGE_EVERY_MIN = 30
N6_OUTAGE_LENGTH_MIN = 5

# The demo nodes. east_m / north_m place each node relative to the site centre.
# Scenarios are described in scenarios.py.
NODES = [
    {"key": "N1", "name": "N1 North crest", "dev_eui": "70b3d57ed0000001", "scenario": "stable",
     "east_m": -180, "north_m": 260, "base_angle_x": 3.2, "base_angle_y": -0.8, "heading": 12.0, "rssi_base": -84},
    {"key": "N2", "name": "N2 North bench", "dev_eui": "70b3d57ed0000002", "scenario": "stable",
     "east_m": 40, "north_m": 210, "base_angle_x": 4.1, "base_angle_y": 0.6, "heading": 355.0, "rssi_base": -91},
    {"key": "N3", "name": "N3 West wall", "dev_eui": "70b3d57ed0000003", "scenario": "stable",
     "east_m": -320, "north_m": -40, "base_angle_x": 2.5, "base_angle_y": 1.4, "heading": 88.0, "rssi_base": -97},
    {"key": "N4", "name": "N4 East wall", "dev_eui": "70b3d57ed0000004", "scenario": "creeping",
     "east_m": 280, "north_m": -60, "base_angle_x": 5.6, "base_angle_y": -1.2, "heading": 271.0, "rssi_base": -88},
    {"key": "N5", "name": "N5 South ramp", "dev_eui": "70b3d57ed0000005", "scenario": "low_battery",
     "east_m": 110, "north_m": -300, "base_angle_x": 3.8, "base_angle_y": 0.2, "heading": 180.0, "rssi_base": -102},
    {"key": "N6", "name": "N6 Pit floor", "dev_eui": "70b3d57ed0000006", "scenario": "faulty",
     "east_m": -60, "north_m": -180, "base_angle_x": 1.9, "base_angle_y": -0.4, "heading": 87.3, "rssi_base": -108},
]
