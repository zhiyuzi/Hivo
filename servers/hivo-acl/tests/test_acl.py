"""Integration tests for hivo-acl API."""
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
import sqlite3

BASE = "http://localhost:8004"
DB_PATH = Path(__file__).parent.parent / "data" / "acl.db"
SUB = "agt_019d3d26-6b3c-7342-bf6e-7f44b7820d55"
OTHER = "agt_other_agent_for_testing"
RESOURCE = "drop:file:test123"
TIMEOUT = 10


@pytest.fixture(scope="session")
def token():
    """Get a fresh token via get_token.py."""
    script = Path(__file__).parent.parent.parent.parent / "skills" / "hivo-identity" / "scripts" / "get_token.py"
    result = subprocess.run(
        [sys.executable, str(script), "acl"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"get_token.py failed: {result.stderr}"
    return result.stdout.strip()


@pytest.fixture(scope="session")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE, timeout=TIMEOUT)


@pytest.fixture(autouse=True, scope="session")
def clean_db():
    """Clear all data before test session."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM grants")
    conn.execute("DELETE FROM audit_log")
    conn.commit()
    conn.close()


class TestBootstrap:
    def test_self_admin(self, client, headers):
        r = client.post("/grants", headers=headers, json={"subject": SUB, "resource": RESOURCE, "action": "admin", "effect": "allow"})
        assert r.status_code == 200
        assert "granted_by" in r.json()

    def test_self_read_write_delete(self, client, headers):
        for action in ["read", "write", "delete"]:
            r = client.post("/grants", headers=headers, json={"subject": SUB, "resource": RESOURCE, "action": action, "effect": "allow"})
            assert r.status_code == 200

    def test_idempotent_regrant(self, client, headers):
        r = client.post("/grants", headers=headers, json={"subject": SUB, "resource": RESOURCE, "action": "admin", "effect": "allow"})
        assert r.status_code == 200


class TestCheck:
    def test_self_read_allowed(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": SUB, "resource": RESOURCE, "action": "read"})
        assert r.json()["allowed"] is True

    def test_other_read_denied(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": OTHER, "resource": RESOURCE, "action": "read"})
        assert r.json()["allowed"] is False


class TestGrantToOther:
    def test_grant_other_read(self, client, headers):
        r = client.post("/grants", headers=headers, json={"subject": OTHER, "resource": RESOURCE, "action": "read", "effect": "allow"})
        assert r.status_code == 200

    def test_other_read_allowed(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": OTHER, "resource": RESOURCE, "action": "read"})
        assert r.json()["allowed"] is True


class TestDenyPriority:
    def test_add_deny(self, client, headers):
        r = client.post("/grants", headers=headers, json={"subject": OTHER, "resource": RESOURCE, "action": "read", "effect": "deny"})
        assert r.status_code == 200

    def test_deny_wins(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": OTHER, "resource": RESOURCE, "action": "read"})
        assert r.json()["allowed"] is False

    def test_revoke_deny(self, client, headers):
        r = client.request("DELETE", "/grants", headers=headers, json={"subject": OTHER, "resource": RESOURCE, "action": "read", "effect": "deny"})
        assert r.status_code == 204

    def test_allowed_after_revoke_deny(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": OTHER, "resource": RESOURCE, "action": "read"})
        assert r.json()["allowed"] is True


class TestIdempotentRevoke:
    def test_delete_nonexistent(self, client, headers):
        r = client.request("DELETE", "/grants", headers=headers, json={"subject": OTHER, "resource": RESOURCE, "action": "delete", "effect": "allow"})
        assert r.status_code == 204


class TestWildcard:
    def test_grant_wildcard(self, client, headers):
        r = client.post("/grants", headers=headers, json={"subject": SUB, "resource": "drop:file:*", "action": "read", "effect": "allow"})
        assert r.status_code == 200

    def test_wildcard_match(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": SUB, "resource": "drop:file:other999", "action": "read"})
        assert r.json()["allowed"] is True

    def test_wildcard_no_match_different_action(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": SUB, "resource": "drop:file:other999", "action": "write"})
        assert r.json()["allowed"] is False


class TestListGrants:
    def test_list(self, client, auth):
        r = client.get("/grants", headers=auth, params={"resource": RESOURCE})
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0


class TestAuditLog:
    def test_audit(self, client, auth):
        r = client.get("/audit", headers=auth, params={"resource": RESOURCE})
        assert r.status_code == 200
        assert len(r.json()) > 0


class TestBulkDelete:
    def test_bulk_delete(self, client, headers):
        r = client.request("DELETE", "/grants", headers=headers, json={"subject": "*", "resource": RESOURCE})
        assert r.status_code == 204

    def test_self_denied_after_bulk(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": SUB, "resource": RESOURCE, "action": "admin"})
        assert r.json()["allowed"] is False

    def test_other_denied_after_bulk(self, client, auth):
        r = client.get("/check", headers=auth, params={"subject": OTHER, "resource": RESOURCE, "action": "read"})
        assert r.json()["allowed"] is False


class TestPublicEndpoints:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "hivo-acl" in r.text
