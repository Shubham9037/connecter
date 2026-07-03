"""MongoDB connection + index bootstrap.

Design note: we keep a single AsyncIOMotorClient at module scope so that all
routers share the connection pool. Indexes are created idempotently on startup
because the security guarantees of the sync endpoint depend on them
(unique idempotency keys, TTL expiry of nonces, etc.).
"""
from __future__ import annotations

import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_mongo_url = os.environ["MONGO_URL"]
_db_name = os.environ["DB_NAME"]

client: AsyncIOMotorClient = AsyncIOMotorClient(_mongo_url)
db: AsyncIOMotorDatabase = client[_db_name]


async def ensure_indexes() -> None:
    """Create all indexes required for correctness + security.

    TTL indexes are Mongo's built-in cleanup. We intentionally avoid a
    background job runner (Module 1A is single-service, MongoDB-only).
    """
    # --- Nonces (replay protection) -------------------------------------------
    # Uniqueness on signature guarantees each signed request is accepted once.
    await db.nonces.create_index("signature", unique=True, name="uniq_signature")
    # TTL fires when expires_at <= now(). We store expires_at as a real
    # datetime so Mongo's TTL monitor can act on it.
    await db.nonces.create_index("expires_at", expireAfterSeconds=0, name="ttl_expires_at")

    # --- Idempotency ----------------------------------------------------------
    # A single (connector_id, idempotency_key) pair may be reused within the
    # TTL to fetch the cached response.
    await db.idempotency_keys.create_index(
        [("connector_id", 1), ("idempotency_key", 1)],
        unique=True,
        name="uniq_connector_idem",
    )
    await db.idempotency_keys.create_index(
        "expires_at", expireAfterSeconds=0, name="ttl_expires_at"
    )

    # --- Connectors -----------------------------------------------------------
    await db.connectors.create_index("connector_id", unique=True, name="uniq_connector_id")
    await db.connectors.create_index(
        [("company_id", 1), ("status", 1)], name="company_status"
    )

    # --- Sync logs ------------------------------------------------------------
    await db.sync_logs.create_index([("created_at", -1)], name="created_at_desc")
    await db.sync_logs.create_index(
        [("connector_id", 1), ("created_at", -1)], name="connector_created"
    )
    await db.sync_logs.create_index(
        [("company_id", 1), ("created_at", -1)], name="company_created"
    )
    await db.sync_logs.create_index([("status", 1)], name="status")

    # --- Security events ------------------------------------------------------
    await db.security_events.create_index([("created_at", -1)], name="created_at_desc")
    await db.security_events.create_index([("event_type", 1)], name="event_type")

    # --- Audit log (admin actions) --------------------------------------------
    await db.audit_log.create_index([("created_at", -1)], name="created_at_desc")

    # --- Sessions (Emergent Google Auth) --------------------------------------
    await db.user_sessions.create_index("session_token", unique=True, name="uniq_session_token")
    await db.user_sessions.create_index(
        "expires_at", expireAfterSeconds=0, name="ttl_expires_at"
    )

    # --- Users ----------------------------------------------------------------
    await db.users.create_index("user_id", unique=True, name="uniq_user_id")
    await db.users.create_index("email", unique=True, name="uniq_email")
