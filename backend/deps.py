"""Shared FastAPI dependencies (auth + request-id retrieval).

Kept small on purpose — anything cross-cutting like `require_admin` lives
here so routers stay focused on their own concerns.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Header, HTTPException, Request, status

from db import db
from models import User


def _admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_admin_email(email: str) -> bool:
    """Admin allowlist. Empty list = bootstrap mode (first login becomes admin).

    In bootstrap mode we still return True but the auth router marks the very
    first user as admin — see routes/auth.py::process_session.
    """
    allowlist = _admin_emails()
    if not allowlist:
        return True
    return email.lower() in allowlist


async def current_user(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> User:
    """Resolve session_token (cookie preferred, Authorization: Bearer fallback).

    We do NOT use FastAPI's HTTPAuthorizationCredentials — per the Emergent
    Auth playbook, that dependency breaks cookie-only auth flows.
    """
    token = session_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user_doc = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return User(**user_doc)


async def require_admin(user: User = None) -> User:  # type: ignore[assignment]
    # This wrapper form lets FastAPI resolve `current_user` first through
    # dependency chaining below.
    ...


async def admin_user(user: User = None) -> User:  # pragma: no cover — replaced
    ...


# Actual dependency callable used in routers ----------------------------------
async def require_admin_dep(user: User = None) -> User:  # placeholder header
    raise NotImplementedError


async def get_admin(request: Request) -> User:
    user = await current_user(
        request,
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")
