"""Pytest fixtures for the Razio backend.

We use FastAPI's TestClient (blocking) with a per-worker Mongo DB so that
xdist parallel workers can't race on collection wipes. Cleanup uses a SYNC
pymongo client — motor's async client binds itself to whatever event loop
first uses it, which fights TestClient's own loop management.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

# Make backend importable and load env BEFORE any project modules
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
load_dotenv(BACKEND_ROOT / ".env")


def _configure_worker_db(worker_id: str) -> None:
    """Assign each xdist worker its own Mongo database.

    xdist doesn't set PYTEST_XDIST_WORKER before conftest imports, so we
    do the env override inside a fixture where the built-in `worker_id`
    fixture is available.
    """
    base = os.environ.get("_RAZIO_DB_BASE") or os.environ.get("DB_NAME", "test_database")
    os.environ["_RAZIO_DB_BASE"] = base
    os.environ["DB_NAME"] = f"{base}_pytest_{worker_id}"


@pytest.fixture(scope="session")
def sync_db(worker_id):
    _configure_worker_db(worker_id)
    mc = MongoClient(os.environ["MONGO_URL"])
    return mc[os.environ["DB_NAME"]]


@pytest.fixture(scope="session")
def app_client(sync_db):
    # Import server AFTER _configure_worker_db has set DB_NAME
    from fastapi.testclient import TestClient
    from server import app

    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _reset_collections(sync_db):
    for col in (
        "connectors",
        "sync_logs",
        "security_events",
        "nonces",
        "idempotency_keys",
        "audit_log",
        "users",
        "user_sessions",
    ):
        sync_db[col].delete_many({})
    yield


@pytest.fixture
def admin_session(sync_db):
    """Insert a fake admin user + session directly (bypasses Emergent Auth)."""
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    token = f"testtok_{uuid.uuid4().hex}"
    sync_db.users.insert_one(
        {
            "user_id": user_id,
            "email": "admin@razio.test",
            "name": "Admin",
            "is_admin": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    sync_db.user_sessions.insert_one(
        {
            "user_id": user_id,
            "session_token": token,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
            "created_at": datetime.now(timezone.utc),
        }
    )
    return token
