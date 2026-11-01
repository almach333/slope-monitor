"""Authentication: password hashing, JWT tokens and the current-user dependency.

Follows the FastAPI "OAuth2 with Password and JWT" tutorial:
- the user sends email + password to POST /api/auth/token,
- the API returns a signed JWT access token,
- the frontend sends it back as "Authorization: Bearer <token>".
"""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

ALGORITHM = "HS256"

# argon2 password hashing (pwdlib's recommended settings).
password_hash = PasswordHash.recommended()

# Tells FastAPI (and the /docs "Authorize" button) where tokens come from.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


# A real hash of a random password, used to spend the same time checking a
# password for an unknown email as for a known one (so attackers can't tell
# which emails exist from the response time).
_DUMMY_HASH = hash_password("not-a-real-password")


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user if the email and password are correct, otherwise None."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user_id: int, expires_minutes: int | None = None) -> tuple[str, int]:
    """Create a signed JWT for a user. Returns (token, seconds until it expires)."""
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM), minutes * 60


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """FastAPI dependency: the logged-in user, or a 401 error.

    Checks the token's signature and expiry, then that the user still
    exists and is active.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        # Covers tampered, expired and malformed tokens.
        raise _unauthorized()
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    """Dependency for admin-only endpoints (none in the MVP, ready for later)."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


class LoginRateLimiter:
    """Very simple in-memory limit on failed logins (enough for a prototype).

    After MAX_FAILURES failed attempts for the same (IP address, email) within
    WINDOW_S seconds, further attempts are refused with 429 until the window
    passes. Resets when the server restarts.
    """

    MAX_FAILURES = 5
    WINDOW_S = 300

    def __init__(self) -> None:
        self._failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _prune(self, key: tuple[str, str], now: float) -> deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.WINDOW_S:
            q.popleft()
        return q

    def retry_after(self, ip: str, email: str) -> int:
        """Seconds until another attempt is allowed (0 = allowed now)."""
        now = time.monotonic()
        q = self._prune((ip, email.lower()), now)
        if len(q) < self.MAX_FAILURES:
            return 0
        return int(self.WINDOW_S - (now - q[0])) + 1

    def record_failure(self, ip: str, email: str) -> None:
        self._failures[(ip, email.lower())].append(time.monotonic())

    def reset(self, ip: str, email: str) -> None:
        self._failures.pop((ip, email.lower()), None)


login_limiter = LoginRateLimiter()
