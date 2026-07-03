"""Admin CRUD for connectors.

Design notes:
- The plaintext secret is returned exactly once, on creation and regeneration.
- We store `secret_encrypted` (Fernet) + `secret_last4` (for UI display).
- Revoke is a soft-delete: `status="revoked"`. Hard delete is deferred.
- Every mutation writes an entry to `audit_log`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from db import db
from deps import get_admin, request_id
from logging_config import app_logger
from models import (
    Connector,
    ConnectorCreate,
    ConnectorPublic,
    ConnectorSecretReveal,
    User,
)
from security import (
    encrypt_secret,
    generate_connector_id,
    generate_secret,
    secret_last4,
)

router = APIRouter(prefix="/api/connectors", tags=["connectors"])
_log = app_logger()


def _to_public(doc: dict) -> ConnectorPublic:
    return ConnectorPublic(**doc)


async def _audit(
    request: Request,
    actor: User,
    action: str,
    connector_id: str,
    metadata: Optional[dict] = None,
) -> None:
    await db.audit_log.insert_one(
        {
            "request_id": getattr(request.state, "request_id", "-"),
            "actor_user_id": actor.user_id,
            "actor_email": actor.email,
            "action": action,
            "target_type": "connector",
            "target_id": connector_id,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
        }
    )


class RevokeReason(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=280)


@router.get("", response_model=list[ConnectorPublic])
async def list_connectors(admin: User = Depends(get_admin)):
    docs = await db.connectors.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [_to_public(d) for d in docs]


@router.post("", response_model=ConnectorSecretReveal, status_code=status.HTTP_201_CREATED)
async def create_connector(
    body: ConnectorCreate,
    request: Request,
    admin: User = Depends(get_admin),
):
    connector_id = generate_connector_id()
    plaintext = generate_secret()
    now = datetime.now(timezone.utc)

    doc = {
        "connector_id": connector_id,
        "name": body.name.strip(),
        "company_id": body.company_id.strip(),
        "status": "active",
        "secret_encrypted": encrypt_secret(plaintext),
        "secret_last4": secret_last4(plaintext),
        "created_at": now,
        "created_by": admin.user_id,
        "last_sync_at": None,
        "last_rotated_at": None,
    }
    await db.connectors.insert_one(doc)
    await _audit(request, admin, "connector.create", connector_id, {"company_id": body.company_id})
    _log.info("connector_created id=%s company=%s by=%s", connector_id, body.company_id, admin.email)

    public = _to_public({**doc, "created_at": now})
    return ConnectorSecretReveal(connector=public, secret=plaintext)


@router.get("/{connector_id}", response_model=ConnectorPublic)
async def get_connector(connector_id: str, admin: User = Depends(get_admin)):
    doc = await db.connectors.find_one({"connector_id": connector_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Connector not found")
    return _to_public(doc)


@router.post("/{connector_id}/regenerate", response_model=ConnectorSecretReveal)
async def regenerate_secret(
    connector_id: str,
    request: Request,
    admin: User = Depends(get_admin),
):
    doc = await db.connectors.find_one({"connector_id": connector_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Connector not found")
    if doc["status"] == "revoked":
        raise HTTPException(status_code=409, detail="Cannot regenerate a revoked connector")

    plaintext = generate_secret()
    now = datetime.now(timezone.utc)
    await db.connectors.update_one(
        {"connector_id": connector_id},
        {
            "$set": {
                "secret_encrypted": encrypt_secret(plaintext),
                "secret_last4": secret_last4(plaintext),
                "last_rotated_at": now,
            }
        },
    )
    await _audit(request, admin, "connector.regenerate", connector_id)
    _log.info("connector_regenerated id=%s by=%s", connector_id, admin.email)

    doc["secret_last4"] = secret_last4(plaintext)
    doc["last_rotated_at"] = now
    return ConnectorSecretReveal(connector=_to_public(doc), secret=plaintext)


@router.post("/{connector_id}/revoke", response_model=ConnectorPublic)
async def revoke_connector(
    connector_id: str,
    body: RevokeReason,
    request: Request,
    admin: User = Depends(get_admin),
):
    doc = await db.connectors.find_one({"connector_id": connector_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Connector not found")
    if doc["status"] == "revoked":
        return _to_public(doc)

    now = datetime.now(timezone.utc)
    await db.connectors.update_one(
        {"connector_id": connector_id},
        {"$set": {"status": "revoked", "revoked_at": now, "revoked_by": admin.user_id}},
    )
    await _audit(
        request,
        admin,
        "connector.revoke",
        connector_id,
        {"reason": body.reason or ""},
    )
    _log.info("connector_revoked id=%s by=%s", connector_id, admin.email)

    doc["status"] = "revoked"
    doc["revoked_at"] = now
    return _to_public(doc)
