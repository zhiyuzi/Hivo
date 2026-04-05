"""Tests for /me, /jwks.json, /.well-known/openid-configuration, /health."""
import time
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.tokens import _jwt_encode
from app.config import settings


def make_assertion(sub: str, private_key, ttl: int = 300) -> str:
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT"}
    payload = {
        "iss": sub,
        "sub": sub,
        "aud": f"{settings.issuer_url}/token",
        "iat": now,
        "exp": now + ttl,
    }
    return _jwt_encode(header, payload, private_key)


def get_tokens(client, sub, key):
    assertion = make_assertion(sub, key)
    r = client.post("/token", json={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "audience": "hivo-identity",
    })
    assert r.status_code == 200
    return r.json()["access_token"], r.json()["refresh_token"]


def test_me_success(client, registered_agent):
    sub, handle, key = registered_agent
    access_token, _ = get_tokens(client, sub, key)

    r = client.get("/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["sub"] == sub
    assert data["handle"] == handle
    assert data["status"] == "active"
    assert data["bio"] is None


def test_patch_me_display_name(client, registered_agent):
    sub, _, key = registered_agent
    access_token, _ = get_tokens(client, sub, key)
    headers = {"Authorization": f"Bearer {access_token}"}

    r = client.patch("/me", headers=headers, json={"display_name": "New Name"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "New Name"

    # Verify persisted
    r = client.get("/me", headers=headers)
    assert r.json()["display_name"] == "New Name"


def test_patch_me_bio(client, registered_agent):
    sub, _, key = registered_agent
    access_token, _ = get_tokens(client, sub, key)
    headers = {"Authorization": f"Bearer {access_token}"}

    r = client.patch("/me", headers=headers, json={"bio": "I am a test agent"})
    assert r.status_code == 200
    assert r.json()["bio"] == "I am a test agent"


def test_patch_me_email(client, registered_agent):
    sub, _, key = registered_agent
    access_token, _ = get_tokens(client, sub, key)
    headers = {"Authorization": f"Bearer {access_token}"}

    r = client.patch("/me", headers=headers, json={"email": "new@example.com"})
    assert r.status_code == 200
    assert r.json()["email"] == "new@example.com"


def test_patch_me_multiple_fields(client, registered_agent):
    sub, _, key = registered_agent
    access_token, _ = get_tokens(client, sub, key)
    headers = {"Authorization": f"Bearer {access_token}"}

    r = client.patch("/me", headers=headers, json={
        "display_name": "Multi",
        "bio": "Updated bio",
        "email": "multi@example.com",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "Multi"
    assert data["bio"] == "Updated bio"
    assert data["email"] == "multi@example.com"


def test_patch_me_empty_body(client, registered_agent):
    sub, _, key = registered_agent
    access_token, _ = get_tokens(client, sub, key)
    headers = {"Authorization": f"Bearer {access_token}"}

    r = client.patch("/me", headers=headers, json={})
    assert r.status_code == 422


def test_patch_me_no_auth(client):
    r = client.patch("/me", json={"bio": "test"})
    assert r.status_code == 401


def test_me_no_auth(client):
    r = client.get("/me")
    assert r.status_code == 401


def test_me_invalid_token(client):
    r = client.get("/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert r.status_code == 401


def test_jwks(client):
    r = client.get("/jwks.json")
    assert r.status_code == 200
    data = r.json()
    assert "keys" in data
    assert len(data["keys"]) > 0
    key = data["keys"][0]
    assert key["kty"] == "OKP"
    assert key["crv"] == "Ed25519"


def test_oidc_config(client):
    r = client.get("/.well-known/openid-configuration")
    assert r.status_code == 200
    data = r.json()
    assert data["issuer"] == settings.issuer_url
    assert "token_endpoint" in data
    assert "jwks_uri" in data
    assert data["token_endpoint_auth_methods_supported"] == ["private_key_jwt"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_markdown(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert "hivo-identity" in r.text


def test_readme_markdown(client):
    """README.md route was removed; verify 404."""
    r = client.get("/README.md")
    assert r.status_code == 404
