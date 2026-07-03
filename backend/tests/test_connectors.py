"""Admin CRUD tests for /api/connectors."""
from __future__ import annotations


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestConnectorCRUD:
    def test_requires_admin(self, app_client):
        r = app_client.get("/api/connectors")
        assert r.status_code == 401

    def test_create_returns_secret_once(self, app_client, admin_session):
        r = app_client.post(
            "/api/connectors",
            json={"name": "Store A", "company_id": "ACME"},
            headers=_auth(admin_session),
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["secret"], "plaintext secret must be present exactly once"
        cid = data["connector"]["connector_id"]
        assert data["connector"]["secret_last4"] == data["secret"][-4:]

        # Subsequent GET must NOT expose the plaintext secret
        got = app_client.get(f"/api/connectors/{cid}", headers=_auth(admin_session))
        assert got.status_code == 200
        assert "secret" not in got.json()

    def test_regenerate_produces_new_secret(self, app_client, admin_session):
        r = app_client.post(
            "/api/connectors",
            json={"name": "Store A", "company_id": "ACME"},
            headers=_auth(admin_session),
        )
        cid = r.json()["connector"]["connector_id"]
        original_secret = r.json()["secret"]

        r2 = app_client.post(f"/api/connectors/{cid}/regenerate", headers=_auth(admin_session))
        assert r2.status_code == 200
        assert r2.json()["secret"] != original_secret

    def test_revoke_marks_status(self, app_client, admin_session):
        r = app_client.post(
            "/api/connectors",
            json={"name": "Store A", "company_id": "ACME"},
            headers=_auth(admin_session),
        )
        cid = r.json()["connector"]["connector_id"]
        rev = app_client.post(
            f"/api/connectors/{cid}/revoke",
            json={"reason": "compromised"},
            headers=_auth(admin_session),
        )
        assert rev.status_code == 200
        assert rev.json()["status"] == "revoked"

    def test_regenerate_revoked_connector_conflict(self, app_client, admin_session):
        r = app_client.post(
            "/api/connectors",
            json={"name": "Store A", "company_id": "ACME"},
            headers=_auth(admin_session),
        )
        cid = r.json()["connector"]["connector_id"]
        app_client.post(f"/api/connectors/{cid}/revoke", json={}, headers=_auth(admin_session))
        r2 = app_client.post(f"/api/connectors/{cid}/regenerate", headers=_auth(admin_session))
        assert r2.status_code == 409

    def test_list_connectors(self, app_client, admin_session):
        for i in range(3):
            app_client.post(
                "/api/connectors",
                json={"name": f"S{i}", "company_id": f"C{i}"},
                headers=_auth(admin_session),
            )
        r = app_client.get("/api/connectors", headers=_auth(admin_session))
        assert r.status_code == 200
        assert len(r.json()) == 3
