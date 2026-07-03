"""End-to-end tests for the hardened /api/tally/sync endpoint.

Every test drives the API via TestClient — no direct calls into private
helpers, so we exercise the same code path a real Windows Connector would.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone


def _make_request(client, connector_id, company_id, secret, body, *, idem_key=None, ts=None, override_sig=None):
    body_bytes = json.dumps(body).encode()
    timestamp = ts or str(int(time.time()))
    idempotency_key = idem_key or f"idem_{uuid.uuid4().hex}"
    canonical = "\n".join(
        [
            timestamp,
            connector_id,
            company_id,
            idempotency_key,
            hashlib.sha256(body_bytes).hexdigest(),
        ]
    )
    signature = override_sig or hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return client.post(
        "/api/tally/sync",
        content=body_bytes,
        headers={
            "X-Signature": signature,
            "X-Timestamp": timestamp,
            "X-Connector-ID": connector_id,
            "X-Company-ID": company_id,
            "X-Idempotency-Key": idempotency_key,
            "Content-Type": "application/json",
        },
    )


def _create_connector_direct(admin_token, client):
    """Use the admin API with a bearer token to create a connector + secret."""
    r = client.post(
        "/api/connectors",
        json={"name": "Test Connector", "company_id": "ACME"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return data["connector"]["connector_id"], data["secret"]


class TestSyncAuth:
    def test_valid_signature_returns_200(self, app_client, admin_session):
        cid, secret = _create_connector_direct(admin_session, app_client)
        r = _make_request(app_client, cid, "ACME", secret, {"entity_type": "voucher", "records": [{"id": 1}]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["records_received"] == 1
        assert r.headers.get("x-request-id", "").startswith("req_")

    def test_invalid_signature_returns_401(self, app_client, admin_session):
        cid, secret = _create_connector_direct(admin_session, app_client)
        r = _make_request(
            app_client,
            cid,
            "ACME",
            secret,
            {"entity_type": "voucher", "records": []},
            override_sig="0" * 64,
        )
        assert r.status_code == 401
        assert r.json()["code"] == "invalid_signature"

    def test_expired_timestamp_returns_401(self, app_client, admin_session):
        cid, secret = _create_connector_direct(admin_session, app_client)
        old_ts = str(int(time.time()) - 3600)  # 1h old
        r = _make_request(app_client, cid, "ACME", secret, {"entity_type": "voucher", "records": []}, ts=old_ts)
        assert r.status_code == 401
        assert r.json()["code"] == "expired_timestamp"

    def test_future_timestamp_returns_401(self, app_client, admin_session):
        cid, secret = _create_connector_direct(admin_session, app_client)
        future = str(int(time.time()) + 3600)
        r = _make_request(app_client, cid, "ACME", secret, {"entity_type": "voucher", "records": []}, ts=future)
        assert r.status_code == 401
        assert r.json()["code"] == "future_timestamp"

    def test_missing_headers_returns_400(self, app_client):
        r = app_client.post("/api/tally/sync", json={"entity_type": "x", "records": []})
        assert r.status_code == 400
        assert r.json()["code"] == "missing_header"

    def test_unknown_connector_returns_401(self, app_client, admin_session):
        # Real signature-shape but the connector doesn't exist
        r = _make_request(app_client, "cn_missing", "ACME", "irrelevant", {"entity_type": "v", "records": []})
        assert r.status_code == 401
        assert r.json()["code"] == "unknown_connector"

    def test_company_mismatch_returns_401(self, app_client, admin_session):
        cid, secret = _create_connector_direct(admin_session, app_client)
        r = _make_request(app_client, cid, "OTHER", secret, {"entity_type": "v", "records": []})
        assert r.status_code == 401
        assert r.json()["code"] == "company_mismatch"

    def test_revoked_connector_returns_401(self, app_client, admin_session):
        cid, secret = _create_connector_direct(admin_session, app_client)
        rev = app_client.post(
            f"/api/connectors/{cid}/revoke",
            json={"reason": "test"},
            headers={"Authorization": f"Bearer {admin_session}"},
        )
        assert rev.status_code == 200
        r = _make_request(app_client, cid, "ACME", secret, {"entity_type": "v", "records": []})
        assert r.status_code == 401
        assert r.json()["code"] == "revoked_connector"


class TestReplayAndIdempotency:
    def test_replay_same_signature_returns_409(self, app_client, admin_session):
        cid, secret = _create_connector_direct(admin_session, app_client)
        body = {"entity_type": "voucher", "records": []}
        ts = str(int(time.time()))
        idem = f"idem_{uuid.uuid4().hex}"

        first = _make_request(app_client, cid, "ACME", secret, body, ts=ts, idem_key=idem)
        assert first.status_code == 200

        # Same signature (same ts + idem + body) — should be blocked as replay
        second = _make_request(app_client, cid, "ACME", secret, body, ts=ts, idem_key=idem)
        assert second.status_code == 409
        assert second.json()["code"] == "replay_detected"

    def test_idempotency_returns_cached_response(self, app_client, admin_session):
        """Different signature but same idempotency key -> cached response."""
        cid, secret = _create_connector_direct(admin_session, app_client)
        idem = f"idem_{uuid.uuid4().hex}"

        first = _make_request(
            app_client, cid, "ACME", secret, {"entity_type": "voucher", "records": [{"a": 1}]}, idem_key=idem
        )
        assert first.status_code == 200
        first_body = first.json()

        # Wait 1s so timestamp differs -> nonce differs, but idem_key same
        time.sleep(1.1)

        second = _make_request(
            app_client, cid, "ACME", secret, {"entity_type": "voucher", "records": [{"a": 2}]}, idem_key=idem
        )
        assert second.status_code == 200
        assert second.headers.get("X-Idempotent-Replayed") == "true"
        # Cached body echoes the ORIGINAL response
        assert second.json()["records_received"] == first_body["records_received"] == 1
