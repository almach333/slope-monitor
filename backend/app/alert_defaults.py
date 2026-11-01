"""Alert parameters and the default rules (handoff.md section 7).

This is the single source of truth for default thresholds. It is used by
the New Device page (via GET /api/alert-rules/defaults), the simulator and
the tests.

The defaults are PLACEHOLDERS for the prototype, not engineering limits.
Site values come from the site's geotechnical engineer / Trigger Action
Response Plan (TARP).
"""

# Parameters an alert rule can watch, with a label and unit for messages.
ALERT_PARAMETERS: dict[str, dict[str, str]] = {
    "tilt_change_total": {"label": "Tilt change", "unit": "°"},
    "slope_angle": {"label": "Slope angle", "unit": "°"},
    "acc_magnitude": {"label": "Acceleration", "unit": " g"},
    "battery_pct": {"label": "Battery", "unit": " %"},
    "displacement_m": {"label": "Movement", "unit": " m"},
    "temperature": {"label": "Temperature", "unit": " °C"},
    "humidity": {"label": "Humidity", "unit": " %RH"},
    "gyro_magnitude": {"label": "Gyroscope", "unit": " °/s"},
    "mag_magnitude": {"label": "Magnetic field", "unit": " µT"},
}

# Parameter name used for system "node offline" alerts (no rule behind them).
OFFLINE_PARAMETER = "offline"

PLACEHOLDER_NOTE = (
    "Threshold values are placeholders for the prototype. Site values come from "
    "the site's geotechnical engineer / Trigger Action Response Plan."
)

DEFAULT_RULES: list[dict] = [
    {
        "parameter": "tilt_change_total",
        "comparator": "gt",
        "warning_threshold": 1.0,
        "critical_threshold": 2.0,
        "consecutive_readings": 3,
        "justification": "Prototype placeholder (handoff default). Replace with site TARP value.",
    },
    {
        # Relative to the node's baseline slope angle: the absolute thresholds
        # are filled in when the baseline is set.
        "parameter": "slope_angle",
        "comparator": "gt",
        "warning_offset": 1.0,
        "critical_offset": 2.0,
        "consecutive_readings": 3,
        "justification": "Prototype placeholder: baseline +1° / +2° (handoff default). Replace with site TARP value.",
    },
    {
        "parameter": "acc_magnitude",
        "comparator": "gt",
        "warning_threshold": 1.2,
        "critical_threshold": 1.5,
        "consecutive_readings": 3,
        "justification": "Prototype placeholder (handoff default). Replace with site TARP value.",
    },
    {
        "parameter": "battery_pct",
        "comparator": "lt",
        "warning_threshold": 20.0,
        "critical_threshold": 10.0,
        "consecutive_readings": 3,
        "justification": "Prototype placeholder (handoff default): replace battery before node goes offline.",
    },
]
