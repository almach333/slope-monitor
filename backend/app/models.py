"""Database tables (SQLAlchemy models).

See handoff.md section 5. Additions from the approved plan:
- Node.baseline_slope_angle / baseline_set_at (needed for the slope-angle rule)
- AlertRule.warning_offset / critical_offset (thresholds relative to baseline)
- AlertRuleChange (audit history of every rule change, for requirement R6)

Derived values (tilt change, magnitudes, displacement...) are NOT stored.
They are computed when read, in app/derived.py, so they stay correct if the
baseline or reference position is changed later.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="engineer")  # "admin" | "engineer"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    dev_eui: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")

    # Reference position used to compute movement (GPS displacement).
    ref_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Tilt baseline. Null until set (automatically after the first valid
    # readings, or manually with "Set baseline now").
    baseline_angle_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_angle_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_slope_angle: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_set_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    # How often the node is expected to send data. Used for offline detection.
    expected_interval_s: Mapped[int] = mapped_column(Integer, default=60)

    # SHA-256 hash of the node's ingest API key (the plain key is shown once).
    api_key_hash: Mapped[str] = mapped_column(String(64), index=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rules: Mapped[list["AlertRule"]] = relationship(back_populates="node", cascade="all, delete-orphan")


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        # The same node can't send two readings with the same timestamp.
        UniqueConstraint("node_id", "ts", name="uq_reading_node_ts"),
        Index("ix_reading_node_ts", "node_id", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime)  # when it was measured
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)  # packet counter

    # Position
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Inclination about each axis (degrees); angle_z is heading
    angle_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    angle_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    angle_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Acceleration (g)
    acc_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    acc_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    acc_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Gyroscope (degrees per second)
    gyro_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyro_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyro_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Magnetic field (microtesla)
    mag_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    mag_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    mag_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Environment
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Power
    battery_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Radio link quality
    rssi: Mapped[float | None] = mapped_column(Float, nullable=True)
    snr: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Data-quality flags, e.g. ["angle_x_out_of_range", "tilt_spike"]
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    # True if quality_flags is not empty (a plain column makes counting easy).
    has_flags: Mapped[bool] = mapped_column(Boolean, default=False)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    parameter: Mapped[str] = mapped_column(String(40))  # see alert_defaults.ALERT_PARAMETERS
    comparator: Mapped[str] = mapped_column(String(2))  # "gt" | "lt"

    # Absolute thresholds. Null means "pending baseline": the rule is
    # relative to the baseline and the node has no baseline yet.
    warning_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Only for baseline-relative rules (slope angle): threshold = baseline + offset.
    warning_offset: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_offset: Mapped[float | None] = mapped_column(Float, nullable=True)

    consecutive_readings: Mapped[int] = mapped_column(Integer, default=3)
    justification: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    node: Mapped[Node] = relationship(back_populates="rules")


class AlertRuleChange(Base):
    """Audit trail: one row every time a rule is created, edited or deleted (R6)."""

    __tablename__ = "alert_rule_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Not a foreign key, so history survives if the rule is deleted.
    rule_id: Mapped[int] = mapped_column(Integer, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(20))  # "created" | "updated" | "deleted" | "baseline"
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    justification: Mapped[str] = mapped_column(Text, default="")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_node_status", "node_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    # Null for system alerts (offline).
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    level: Mapped[str] = mapped_column(String(10))  # "warning" | "critical"
    parameter: Mapped[str] = mapped_column(String(40))  # rule parameter, or "offline"
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(15), default="open")  # "open" | "acknowledged" | "resolved"
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    node: Mapped[Node] = relationship()
