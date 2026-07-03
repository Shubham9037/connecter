"""Pydantic models for Razio Connect.

We intentionally avoid a heavy BaseDocument abstraction (see coding
guidelines: no unnecessary abstractions). All Mongo documents use plain
Pydantic models plus small helpers. Every read query MUST use `{"_id": 0}`
projection so that Mongo's internal `_id` never leaks into the API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums / literals
# ---------------------------------------------------------------------------
ConnectorStatus = Literal["active", "revoked"]
SyncStatus = Literal["success", "failed", "duplicate", "replayed"]
SecurityEventType = Literal[
    "invalid_signature",
    "expired_timestamp",
    "future_timestamp",
    "replay_attempt",
    "missing_header",
    "unknown_connector",
    "revoked_connector",
    "company_mismatch",
    "malformed_payload",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------
class Connector(BaseModel):
    """A per-company Windows Connector credential.

    `secret_encrypted` holds the Fernet-encrypted HMAC secret. The plaintext
    secret is only ever returned once, at creation/regeneration time, via the
    one-time reveal API response — never persisted or logged.
    """

    model_config = ConfigDict(extra="ignore")

    connector_id: str
    name: str
    company_id: str
    status: ConnectorStatus = "active"
    secret_encrypted: str
    secret_last4: str
    created_at: datetime = Field(default_factory=_utcnow)
    created_by: str  # admin user_id
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_rotated_at: Optional[datetime] = None


class ConnectorPublic(BaseModel):
    """Connector shape returned to admin UI — never includes the secret."""

    connector_id: str
    name: str
    company_id: str
    status: ConnectorStatus
    secret_last4: str
    created_at: datetime
    last_sync_at: Optional[datetime] = None
    last_rotated_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ConnectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    company_id: str = Field(min_length=1, max_length=120)


class ConnectorSecretReveal(BaseModel):
    """One-time payload shown on creation or regeneration."""

    connector: ConnectorPublic
    secret: str  # PLAINTEXT — client MUST persist immediately.
    note: str = (
        "Store this secret in your Windows Connector configuration now. "
        "It cannot be retrieved later; you would need to regenerate."
    )


# ---------------------------------------------------------------------------
# Sync log
# ---------------------------------------------------------------------------
class SyncLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request_id: str
    connector_id: str
    company_id: str
    idempotency_key: str
    status: SyncStatus
    http_status: int
    entity_type: Optional[str] = None
    record_count: int = 0
    cursor_in: Optional[str] = None
    cursor_out: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Security event
# ---------------------------------------------------------------------------
class SecurityEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request_id: str
    event_type: SecurityEventType
    connector_id: Optional[str] = None
    company_id: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Audit log (admin actions)
# ---------------------------------------------------------------------------
class AuditLogEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request_id: str
    actor_user_id: str
    actor_email: str
    action: str  # e.g. "connector.create", "connector.revoke"
    target_type: str  # e.g. "connector"
    target_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# User + Session (Emergent Google Auth)
# ---------------------------------------------------------------------------
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    is_admin: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    last_login_at: Optional[datetime] = None


class Session(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Sync request body
# ---------------------------------------------------------------------------
class TallySyncPayload(BaseModel):
    """Incremental sync envelope from the Windows Connector.

    Deep Tally schema mapping (masters, vouchers) is deferred to Module 1B.
    For 1A we accept a generic envelope and persist raw payload metadata only.
    """

    entity_type: str = Field(min_length=1, max_length=64)
    records: list[dict[str, Any]] = Field(default_factory=list)
    cursor: Optional[str] = Field(default=None, max_length=256)
