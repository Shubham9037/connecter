"""Emergent-managed Google Auth.

Flow (see /app/auth_testing.md):
  1. Frontend redirects to https://auth.emergentagent.com/?redirect=<origin>/dashboard
  2. Google auth happens externally; user lands back at redirect#session_id=...
  3. Frontend calls POST /api/auth/session { session_id }
  4. Backend exchanges via demobackend.emergentagent.com and creates a session
     + httpOnly cookie.

REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS,
THIS BREAKS THE AUTH.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from db import db
from deps import current_user, is_admin_email
from logging_config import app_logger
from models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
_SESSION_TTL = timedelta(days=7)
_log = app_logger()


class SessionExchangeRequest(BaseModel):
    session_id: str


@router.post("/session")
async def exchange_session(payload: SessionExchangeRequest, response: Response):
    """Trade an Emergent Auth session_id for a persistent session cookie."""
    if not payload.session_id or len(payload.session_id) < 8:
        raise HTTPException(status_code=400, detail="Missing session_id")

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            _EMERGENT_SESSION_URL,
            headers={"X-Session-ID": payload.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Session exchange failed")
    data = r.json()

    email = data["email"]
    name = data.get("name") or email
    picture = data.get("picture")
    session_token = data["session_token"]

    # Upsert user. First user overall becomes admin (bootstrap); after that,
    # the ADMIN_EMAILS allowlist governs admin status.
    total_users = await db.users.count_documents({})
    email_grants_admin = is_admin_email(email) if total_users > 0 else True

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    now = datetime.now(timezone.utc)
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "name": name,
                    "picture": picture,
                    "is_admin": existing.get("is_admin") or email_grants_admin,
                    "last_login_at": now.isoformat(),
                }
            },
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one(
            {
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "is_admin": email_grants_admin,
                "created_at": now.isoformat(),
                "last_login_at": now.isoformat(),
            }
        )

    # Store session
    expires_at = now + _SESSION_TTL
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {
            "$set": {
                "user_id": user_id,
                "session_token": session_token,
                "expires_at": expires_at,  # BSON date so TTL fires
                "created_at": now,
            }
        },
        upsert=True,
    )

    # httpOnly cookie — samesite=None + secure=True so it works across the
    # emergentagent preview domains (frontend and backend are on subdomains).
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=int(_SESSION_TTL.total_seconds()),
        path="/",
    )
    _log.info("session_created user_id=%s email=%s admin=%s", user_id, email, email_grants_admin)

    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "is_admin": email_grants_admin or (existing and existing.get("is_admin")),
    }


@router.get("/me")
async def me(user: User = Depends(current_user)):
    return user.model_dump()


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token") or ""
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}
