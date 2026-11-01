"""Shared test fixtures.

Every test gets a fresh in-memory SQLite database, so tests never touch
the real slope_monitor.db and can't affect each other.
"""

import math
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password, login_limiter
from app.db import Base, get_db
from app.main import app
from app.models import User

PASSWORD = "correct-horse-battery"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db):
    # Use the test database instead of the real one. The TestClient is not
    # used as a context manager, so the background offline checker doesn't start.
    app.dependency_overrides[get_db] = lambda: db
    login_limiter._failures.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db) -> User:
    u = User(email="engineer@example.com", name="Test Engineer", role="engineer", password_hash=hash_password(PASSWORD))
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def auth(client, user) -> dict:
    """Authorization header for the test user."""
    r = client.post("/api/auth/token", data={"username": user.email, "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register_node(client, auth, rules=None, dev_eui="70b3d57ed00000aa", interval=60, **extra):
    """Register a node through the API. Returns (node dict, api key)."""
    body = {
        "name": "Test node",
        "dev_eui": dev_eui,
        "ref_lat": -27.5,
        "ref_lon": 153.0,
        "expected_interval_s": interval,
        "rules": rules or [],
        **extra,
    }
    r = client.post("/api/nodes", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()["node"], r.json()["api_key"]


def make_reading(dev_eui: str, ts: datetime, angle_x=5.0, angle_y=0.0, **overrides) -> dict:
    """A realistic reading: the accelerometer agrees with the angles (node at rest)."""
    tx, ty = math.radians(angle_x), math.radians(angle_y)
    reading = {
        "dev_eui": dev_eui,
        "ts": ts.isoformat(),
        "lat": -27.5,
        "lon": 153.0,
        "angle_x": angle_x,
        "angle_y": angle_y,
        "acc_x": math.sin(tx),
        "acc_y": math.sin(ty) * math.cos(tx),
        "acc_z": math.cos(tx) * math.cos(ty),
        "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0,
        "mag_x": 22.0, "mag_y": 5.0, "mag_z": -44.0,
        "temperature": 22.0,
        "humidity": 60.0,
        "battery_pct": 90.0,
        "rssi": -90,
        "snr": 5.0,
    }
    reading.update(overrides)
    return reading


def ingest(client, api_key: str, payload):
    return client.post("/api/ingest", json=payload, headers={"X-API-Key": api_key})


@pytest.fixture
def t0() -> datetime:
    """A start time two hours ago, on a whole minute."""
    return (datetime.now(timezone.utc) - timedelta(hours=2)).replace(second=0, microsecond=0)
