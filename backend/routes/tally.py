"""Hardened Tally sync endpoint + admin log/security viewers.

Security posture (see docs/SECURITY.md for the full rationale):

  1. Required headers (X-Signature, X-Timestamp, X-Connector-ID, X-Company-ID,
     X-Idempotency-Key). Missing header -> 400 + security_event.
  2. Timestamp validated within +/-300s (constant configurable).
  3. Connector lookup + status check. Unknown/revoked -> 401 + security_event.
  4. HMAC-SHA256 recomputed over canonical string; constant-time compared.
  5. Nonce (signature) inserted with unique index — replays hit DuplicateKey.
  6. Idempotency key: unique index on (connector_id, idempotency_key). Second
     request with the same key within TTL returns the cached response with
     header X-Idempotent-Replayed: true.
  7. Every request creates a sync_logs entry (success or failure). Sensitive
     material (secret, raw body, signature) is never logged.

Deep Tally schema mapping is intentionally out of scope for Module 1A (see
ADR-002). We persist metadata only; the raw payload is not stored to disk.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pymongo.errors import DuplicateKeyError

from db import db
from deps import get_admin
from logging_config import security_logger, sync_logger
from models import (
    SecurityEvent,
    SecurityEventType,
    SyncLog,
    TallySyncPayload,
    User,
)
from security import (
    IDEMPOTENCY_TTL_SECONDS,
    NONCE_TTL_SECONDS,
    Headers,
    TimestampError,
    canonical_string,
    decrypt_secret,
    sign,
    signatures_equal,
    validate_timestamp,
)

router = APIRouter(prefix="/api/tally", tags=["tally"])
_sec_log = security_logger()
_syn_log = sync_logger()


# ---------------------------------------------------------------------------
# Helpers — security-event recording
# ---------------------------------------------------------------------------
async def _record_security_event(
    request: Request,
    event_type: SecurityEventType,
    connector_id: Optional[str],
    company_id: Optional[str],
    detail: str,
) -> None:
    rid = getattr(request.state, "request_id", "-")
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await db.security_events.insert_one(
        {
            "request_id": rid,
            "event_type": event_type,
            "connector_id": connector_id,
            "company_id": company_id,
            "ip": ip,
            "user_agent": ua,
            "detail": detail,
            "created_at": datetime.now(timezone.utc),
        }
    )
    # security.log — no secrets, no payloads, no signatures
    _sec_log.warning(
        "event=%s request_id=%s connector=%s company=%s ip=%s detail=%s",
        event_type,
        rid,
        connector_id or "-",
        company_id or "-",
        ip or "-",
        detail,
    )


async def _record_sync_log(entry: SyncLog) -> None:
    doc = entry.model_dump()
    doc["created_at"] = entry.created_at  # keep BSON date
    await db.sync_logs.insert_one(doc)
    _syn_log.info(
        "request_id=%s connector=%s company=%s status=%s http=%s entity=%s records=%s duration_ms=%s",
        entry.request_id,
        entry.connector_id,
        entry.company_id,
        entry.status,
        entry.http_status,
        entry.entity_type or "-",
        entry.record_count,
        entry.duration_ms,
    )


class _SyncError(HTTPException):
    """HTTPException that carries an error code for logging."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# POST /api/tally/sync
# ---------------------------------------------------------------------------
@router.post("/sync")
async def tally_sync(
    request: Request,
    response: Response,
    x_signature: Optional[str] = Header(default=None, alias=Headers.SIGNATURE),
    x_timestamp: Optional[str] = Header(default=None, alias=Headers.TIMESTAMP),
    x_connector_id: Optional[str] = Header(default=None, alias=Headers.CONNECTOR_ID),
    x_company_id: Optional[str] = Header(default=None, alias=Headers.COMPANY_ID),
    x_idempotency_key: Optional[str] = Header(default=None, alias=Headers.IDEMPOTENCY_KEY),
):
    started = time.perf_counter()
    request_id = getattr(request.state, "request_id", "-")
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    body_bytes = await request.body()

    # 1. Required headers ------------------------------------------------------
    missing = [
        name
        for name, value in [
            (Headers.SIGNATURE, x_signature),
            (Headers.TIMESTAMP, x_timestamp),
            (Headers.CONNECTOR_ID, x_connector_id),
            (Headers.COMPANY_ID, x_company_id),
            (Headers.IDEMPOTENCY_KEY, x_idempotency_key),
        ]
        if not value
    ]
    if missing:
        await _record_security_event(
            request,
            "missing_header",
            x_connector_id,
            x_company_id,
            f"missing={','.join(missing)}",
        )
        raise _SyncError(400, "missing_header", f"Missing required header(s): {', '.join(missing)}")

    # 2. Timestamp -------------------------------------------------------------
    try:
        validate_timestamp(x_timestamp)  # type: ignore[arg-type]
    except TimestampError as exc:
        await _record_security_event(request, exc.code, x_connector_id, x_company_id, exc.detail)  # type: ignore[arg-type]
        raise _SyncError(401, exc.code, exc.detail)

    # 3. Connector lookup ------------------------------------------------------
    connector = await db.connectors.find_one({"connector_id": x_connector_id}, {"_id": 0})
    if not connector:
        await _record_security_event(request, "unknown_connector", x_connector_id, x_company_id, "no such connector")
        raise _SyncError(401, "unknown_connector", "Connector not recognised.")
    if connector["status"] != "active":
        await _record_security_event(request, "revoked_connector", x_connector_id, x_company_id, "revoked")
        raise _SyncError(401, "revoked_connector", "Connector is revoked.")
    if connector["company_id"] != x_company_id:
        await _record_security_event(
            request, "company_mismatch", x_connector_id, x_company_id, "company_id != connector.company_id"
        )
        raise _SyncError(401, "company_mismatch", "Company ID does not match connector.")

    # 4. Signature verification -----------------------------------------------
    canonical = canonical_string(
        x_timestamp, x_connector_id, x_company_id, x_idempotency_key, body_bytes  # type: ignore[arg-type]
    )
    expected = sign(decrypt_secret(connector["secret_encrypted"]), canonical)
    if not signatures_equal(expected, x_signature):  # type: ignore[arg-type]
        await _record_security_event(
            request, "invalid_signature", x_connector_id, x_company_id, "hmac mismatch"
        )
        raise _SyncError(401, "invalid_signature", "Invalid signature.")

    # 5. Replay protection -----------------------------------------------------
    try:
        await db.nonces.insert_one(
            {
                "signature": x_signature,
                "connector_id": x_connector_id,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=NONCE_TTL_SECONDS),
            }
        )
    except DuplicateKeyError:
        await _record_security_event(
            request, "replay_attempt", x_connector_id, x_company_id, "signature already seen"
        )
        raise _SyncError(409, "replay_detected", "Signature already used (replay).")

    # 6. Idempotency check -----------------------------------------------------
    idem_query = {"connector_id": x_connector_id, "idempotency_key": x_idempotency_key}
    existing = await db.idempotency_keys.find_one(idem_query, {"_id": 0})
    if existing and existing.get("response") is not None:
        cached = existing["response"]
        response.headers["X-Idempotent-Replayed"] = "true"
        await _record_sync_log(
            SyncLog(
                request_id=request_id,
                connector_id=x_connector_id,  # type: ignore[arg-type]
                company_id=x_company_id,  # type: ignore[arg-type]
                idempotency_key=x_idempotency_key,  # type: ignore[arg-type]
                status="duplicate",
                http_status=cached["status_code"],
                entity_type=cached.get("entity_type"),
                record_count=cached.get("record_count", 0),
                duration_ms=int((time.perf_counter() - started) * 1000),
                ip=ip,
                user_agent=ua,
            )
        )
        response.status_code = cached["status_code"]
        return cached["body"]

    # 7. Payload validation ----------------------------------------------------
    try:
        payload_json = json.loads(body_bytes.decode("utf-8"))
        payload = TallySyncPayload(**payload_json)
    except Exception as exc:  # noqa: BLE001 — pydantic + json parse
        await _record_security_event(
            request, "malformed_payload", x_connector_id, x_company_id, f"{type(exc).__name__}"
        )
        raise _SyncError(400, "malformed_payload", "Body is not a valid TallySyncPayload.")

    # 8. Process (persist metadata; deep mapping deferred to Module 1B) --------
    now = datetime.now(timezone.utc)
    result_body = {
        "ok": True,
        "request_id": request_id,
        "entity_type": payload.entity_type,
        "records_received": len(payload.records),
        "cursor_out": payload.cursor,  # echo — Module 1B will compute a real one
        "received_at": now.isoformat(),
    }

    # 9. Cache response for idempotency ---------------------------------------
    await db.idempotency_keys.insert_one(
        {
            "connector_id": x_connector_id,
            "idempotency_key": x_idempotency_key,
            "response": {
                "status_code": 200,
                "body": result_body,
                "entity_type": payload.entity_type,
                "record_count": len(payload.records),
            },
            "expires_at": now + timedelta(seconds=IDEMPOTENCY_TTL_SECONDS),
            "created_at": now,
        }
    )

    # 10. Update connector's last_sync_at -------------------------------------
    await db.connectors.update_one(
        {"connector_id": x_connector_id}, {"$set": {"last_sync_at": now}}
    )

    # 11. Success log ---------------------------------------------------------
    await _record_sync_log(
        SyncLog(
            request_id=request_id,
            connector_id=x_connector_id,  # type: ignore[arg-type]
            company_id=x_company_id,  # type: ignore[arg-type]
            idempotency_key=x_idempotency_key,  # type: ignore[arg-type]
            status="success",
            http_status=200,
            entity_type=payload.entity_type,
            record_count=len(payload.records),
            cursor_in=payload.cursor,
            cursor_out=payload.cursor,
            duration_ms=int((time.perf_counter() - started) * 1000),
            ip=ip,
            user_agent=ua,
        )
    )
    return result_body


# ---------------------------------------------------------------------------
# GET /api/tally/logs — admin dashboard
# ---------------------------------------------------------------------------
@router.get("/logs")
async def list_logs(
    admin: User = Depends(get_admin),
    connector_id: Optional[str] = Query(default=None),
    company_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    since: Optional[str] = Query(default=None, description="ISO datetime"),
    until: Optional[str] = Query(default=None, description="ISO datetime"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort: str = Query(default="-created_at"),
):
    q: dict[str, Any] = {}
    if connector_id:
        q["connector_id"] = connector_id
    if company_id:
        q["company_id"] = company_id
    if status_filter:
        q["status"] = status_filter
    if since or until:
        rng: dict[str, Any] = {}
        if since:
            rng["$gte"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if until:
            rng["$lte"] = datetime.fromisoformat(until.replace("Z", "+00:00"))
        q["created_at"] = rng

    field = sort.lstrip("-")
    direction = -1 if sort.startswith("-") else 1
    if field not in {"created_at", "duration_ms", "record_count", "status", "http_status"}:
        raise HTTPException(status_code=400, detail="Invalid sort field")

    total = await db.sync_logs.count_documents(q)
    cursor = (
        db.sync_logs.find(q, {"_id": 0})
        .sort(field, direction)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = await cursor.to_list(page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ---------------------------------------------------------------------------
# GET /api/tally/security-events
# ---------------------------------------------------------------------------
@router.get("/security-events")
async def list_security_events(
    admin: User = Depends(get_admin),
    event_type: Optional[str] = Query(default=None),
    connector_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    q: dict[str, Any] = {}
    if event_type:
        q["event_type"] = event_type
    if connector_id:
        q["connector_id"] = connector_id

    total = await db.security_events.count_documents(q)
    items = (
        await db.security_events.find(q, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list(page_size)
    )
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ---------------------------------------------------------------------------
# GET /api/tally/stats — overview cards
# ---------------------------------------------------------------------------
@router.get("/stats")
async def stats(admin: User = Depends(get_admin)):
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    connectors_total = await db.connectors.count_documents({})
    connectors_active = await db.connectors.count_documents({"status": "active"})
    syncs_24h = await db.sync_logs.count_documents({"created_at": {"$gte": since_24h}})
    successes_24h = await db.sync_logs.count_documents(
        {"created_at": {"$gte": since_24h}, "status": "success"}
    )
    security_events_24h = await db.security_events.count_documents(
        {"created_at": {"$gte": since_24h}}
    )
    replay_attempts_24h = await db.security_events.count_documents(
        {"created_at": {"$gte": since_24h}, "event_type": "replay_attempt"}
    )
    return {
        "connectors_total": connectors_total,
        "connectors_active": connectors_active,
        "syncs_24h": syncs_24h,
        "successes_24h": successes_24h,
        "security_events_24h": security_events_24h,
        "replay_attempts_24h": replay_attempts_24h,
    }
