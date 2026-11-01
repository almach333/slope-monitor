"""R1: browser access with authorised-user login (OAuth 2.0 password flow + bearer JWT)."""

from datetime import datetime, timedelta, timezone

import jwt

from app.auth import ALGORITHM
from app.config import settings
from tests.conftest import PASSWORD


def test_correct_login_returns_bearer_token(client, user):
    """R1: a correct email and password returns a bearer token."""
    r = client.post("/api/auth/token", data={"username": user.email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_wrong_password_and_unknown_email_get_same_401(client, user):
    """R1: a wrong password returns 401, and an unknown email gets the same message."""
    wrong = client.post("/api/auth/token", data={"username": user.email, "password": "nope-nope"})
    unknown = client.post("/api/auth/token", data={"username": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == "Incorrect email or password"


def test_inactive_user_cannot_get_token(client, db, user):
    """R1: an inactive user can't get a token."""
    user.is_active = False
    db.commit()
    r = client.post("/api/auth/token", data={"username": user.email, "password": PASSWORD})
    assert r.status_code == 401


def test_protected_endpoint_without_token_is_401(client):
    """R1: protected endpoints return 401 with a WWW-Authenticate: Bearer header when there's no token."""
    r = client.get("/api/nodes")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_tampered_token_is_rejected(client, auth):
    """R1: a token whose signature doesn't match is rejected."""
    token = auth["Authorization"].split()[1]
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-2]}xx"
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_token_signed_with_other_key_is_rejected(client, user):
    """R1: a token signed with a different secret is rejected."""
    now = datetime.now(timezone.utc)
    forged = jwt.encode({"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=5)}, "x" * 40, algorithm=ALGORITHM)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_is_rejected(client, user):
    """R1: an expired token is rejected."""
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    expired = jwt.encode(
        {"sub": str(user.id), "iat": past, "exp": past + timedelta(minutes=60)}, settings.SECRET_KEY, algorithm=ALGORITHM
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_me_returns_the_logged_in_user(client, auth, user):
    """R1: a valid token returns the right user from /api/auth/me."""
    r = client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["email"] == user.email
    assert "password_hash" not in r.json()


def test_token_of_deactivated_user_stops_working(client, db, auth, user):
    """R1: deactivating a user locks them out even with a valid token."""
    user.is_active = False
    db.commit()
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_repeated_failed_logins_are_rate_limited(client, user):
    """R1 (security): after 5 failed attempts, further logins are refused with 429."""
    for _ in range(5):
        assert client.post("/api/auth/token", data={"username": user.email, "password": "bad"}).status_code == 401
    r = client.post("/api/auth/token", data={"username": user.email, "password": PASSWORD})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
