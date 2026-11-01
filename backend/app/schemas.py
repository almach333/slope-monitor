"""Pydantic schemas: the shapes of data going in and out of the API."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.alert_defaults import ALERT_PARAMETERS

# ---------------------------------------------------------------- auth / users


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


# ---------------------------------------------------------------- ingest


class ReadingIn(BaseModel):
    """One reading sent by a node (handoff.md section 6). All sensor fields are optional."""

    # Ignore unknown fields so newer firmware with extra fields still works.
    model_config = ConfigDict(extra="ignore")

    dev_eui: str
    ts: datetime | None = None  # if missing, the server uses the time it was received
    seq: int | None = None
    lat: float | None = None
    lon: float | None = None
    angle_x: float | None = None
    angle_y: float | None = None
    angle_z: float | None = None
    acc_x: float | None = None
    acc_y: float | None = None
    acc_z: float | None = None
    gyro_x: float | None = None
    gyro_y: float | None = None
    gyro_z: float | None = None
    mag_x: float | None = None
    mag_y: float | None = None
    mag_z: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    battery_pct: float | None = None
    battery_v: float | None = None
    rssi: float | None = None
    snr: float | None = None

    @field_validator("dev_eui")
    @classmethod
    def normalise_dev_eui(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("ts")
    @classmethod
    def assume_utc(cls, v: datetime | None) -> datetime | None:
        # A timestamp without a timezone is treated as UTC.
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v


class IngestResult(BaseModel):
    stored: int = 0
    duplicates: int = 0
    flagged: int = 0
    rejected: int = 0
    duplicate: bool = False  # True when a single reading was a duplicate
    errors: list[str] = []


# ---------------------------------------------------------------- alert rules

Comparator = Literal["gt", "lt"]
AlertParameter = Literal[tuple(ALERT_PARAMETERS)]  # type: ignore[valid-type]


def check_order(comparator: str, warning: float | None, critical: float | None, what: str) -> None:
    """For 'gt' rules critical must be above warning; for 'lt' rules below it."""
    if warning is None or critical is None:
        return
    if comparator == "gt" and not critical > warning:
        raise ValueError(f"For 'greater than' rules the critical {what} must be above the warning {what}")
    if comparator == "lt" and not critical < warning:
        raise ValueError(f"For 'less than' rules the critical {what} must be below the warning {what}")


class AlertRuleBase(BaseModel):
    parameter: AlertParameter
    comparator: Comparator
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    warning_offset: float | None = None
    critical_offset: float | None = None
    consecutive_readings: int = Field(3, ge=1, le=20)
    enabled: bool = True
    # Required (R6): why this limit was chosen, e.g. a TARP reference.
    justification: str = Field(min_length=10, max_length=2000)

    @field_validator("justification")
    @classmethod
    def strip_justification(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Justification is required (at least 10 characters)")
        return v

    @model_validator(mode="after")
    def check_thresholds(self):
        has_abs = self.warning_threshold is not None and self.critical_threshold is not None
        has_off = self.warning_offset is not None and self.critical_offset is not None
        if not has_abs and not has_off:
            raise ValueError("Give both warning and critical thresholds (or both baseline offsets)")
        if has_off and self.parameter != "slope_angle":
            raise ValueError("Baseline offsets are only supported for the slope_angle parameter")
        check_order(self.comparator, self.warning_threshold, self.critical_threshold, "threshold")
        check_order(self.comparator, self.warning_offset, self.critical_offset, "offset")
        return self


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    """Partial update. Justification is always required when changing a rule (R6)."""

    comparator: Comparator | None = None
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    warning_offset: float | None = None
    critical_offset: float | None = None
    consecutive_readings: int | None = Field(None, ge=1, le=20)
    enabled: bool | None = None
    justification: str = Field(min_length=10, max_length=2000)

    @field_validator("justification")
    @classmethod
    def strip_justification(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Justification is required (at least 10 characters)")
        return v


class AlertRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    parameter: str
    comparator: str
    warning_threshold: float | None
    critical_threshold: float | None
    warning_offset: float | None
    critical_offset: float | None
    consecutive_readings: int
    justification: str
    enabled: bool
    updated_by: int | None
    updated_at: datetime
    pending_baseline: bool = False


class AlertRuleChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    node_id: int
    action: str
    changed_by: int | None
    changed_by_name: str | None = None
    changed_at: datetime
    old_values: dict | None
    new_values: dict | None
    justification: str


class AlertDefaults(BaseModel):
    rules: list[dict]
    parameters: dict[str, dict[str, str]]
    note: str


# ---------------------------------------------------------------- nodes


class NodeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dev_eui: str = Field(pattern=r"^[0-9a-fA-F]{16}$", description="16 hex characters")
    description: str = ""
    ref_lat: float | None = Field(None, ge=-90, le=90)
    ref_lon: float | None = Field(None, ge=-180, le=180)
    expected_interval_s: int = Field(60, ge=5, le=86400)
    rules: list[AlertRuleCreate] = []

    @field_validator("dev_eui")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class NodeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    ref_lat: float | None = Field(None, ge=-90, le=90)
    ref_lon: float | None = Field(None, ge=-180, le=180)
    expected_interval_s: int | None = Field(None, ge=5, le=86400)
    baseline_angle_x: float | None = None
    baseline_angle_y: float | None = None
    is_active: bool | None = None


class BaselineRequest(BaseModel):
    readings: int = Field(10, ge=1, le=500, description="Use the median of this many recent valid readings")


class LatestReading(BaseModel):
    ts: datetime
    received_at: datetime
    seq: int | None
    values: dict[str, float | None]
    quality_flags: list[str]


class NodeOut(BaseModel):
    id: int
    name: str
    dev_eui: str
    description: str
    ref_lat: float | None
    ref_lon: float | None
    baseline_angle_x: float | None
    baseline_angle_y: float | None
    baseline_slope_angle: float | None
    baseline_set_at: datetime | None
    expected_interval_s: int
    created_at: datetime
    is_active: bool
    status: Literal["ok", "warning", "critical", "offline"]
    last_seen: datetime | None
    latest: LatestReading | None
    active_alerts: dict[str, int]  # {"warning": n, "critical": n}


class NodeCounts(BaseModel):
    uplinks: int
    flagged: int
    missed: int


class NodeDetail(NodeOut):
    counts: NodeCounts


class NodeCreated(BaseModel):
    node: NodeOut
    api_key: str  # shown ONCE, never stored in plain text


class ApiKeyOut(BaseModel):
    api_key: str


# ---------------------------------------------------------------- readings


class ReadingSeries(BaseModel):
    node_id: int
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    bucket_s: int
    fields: list[str]
    # Each point: {"ts": ..., "flagged": bool, <field>: value or null, ...}
    points: list[dict]


class SeriesLine(BaseModel):
    node_id: int
    name: str
    points: list[dict]  # {"ts": ..., "v": value or null}


class MultiSeries(BaseModel):
    field: str
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    bucket_s: int
    series: list[SeriesLine]


class ReadingRow(BaseModel):
    id: int
    node_id: int
    node_name: str
    ts: datetime
    received_at: datetime
    seq: int | None
    values: dict[str, float | None]
    quality_flags: list[str]


class ReadingPage(BaseModel):
    items: list[ReadingRow]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------- alerts / dashboard


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    node_name: str = ""
    rule_id: int | None
    level: str
    parameter: str
    value: float | None
    threshold: float | None
    message: str
    status: str
    opened_at: datetime
    acknowledged_by: int | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int


class DashboardSummary(BaseModel):
    server_time: datetime
    counts: dict[str, int]  # nodes, online, offline, alerts_warning, alerts_critical, alerts_active, alerts_new
    nodes: list[NodeOut]
    active_alerts: list[AlertOut]
