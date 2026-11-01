"""Login (OAuth 2.0 password flow) and the current user (requirement R1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import CurrentUser, authenticate_user, create_access_token, login_limiter
from app.db import get_db, utcnow
from app.schemas import Token, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Same message for a wrong password and an unknown email, so the response
# doesn't reveal which emails have accounts.
LOGIN_FAILED = "Incorrect email or password"


@router.post("/token", response_model=Token)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    """Exchange email (sent as `username`) + password for a bearer token."""
    ip = request.client.host if request.client else "unknown"
    wait = login_limiter.retry_after(ip, form.username)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )

    user = authenticate_user(db, form.username, form.password)
    if user is None or not user.is_active:
        login_limiter.record_failure(ip, form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOGIN_FAILED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_limiter.reset(ip, form.username)
    user.last_login_at = utcnow()
    db.commit()
    token, expires_in = create_access_token(user.id)
    return Token(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    """The currently logged-in user."""
    return user
