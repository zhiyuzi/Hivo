"""Tests for /token and /token/refresh."""
import base64
import json
import time
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.tokens import _b64url_encode, _jwt_encode


def make_assertion(sub: str, private_key: Ed25519PrivateKey, issuer_url: str, ttl: int = 300) -> str:
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT"}
    payload = {
        "iss": sub,
        "sub": sub,
        "aud": f"{issuer_url}/token",
        "iat": now,
        "exp": now + ttl,
    }
    return _jwt_encode(header, payload, private_key)


def test_token_success(client, registered_agent):
    sub, handle, key = registered_agent
    from app.config import settings
    assertion = make_assertion(sub, key, settings.issuer_url)
    r = client.post("/token", json={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "audience": "test-service",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 3600


def test_token_invalid_sub(client, agent_key):
    from app.config import settings
    assertion = make_assertion("agt_nonexistent", agent_key, settings.issuer_url)
    r = client.post("/token", json={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "audience": "test-service",
    })
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_assertion"


def test_token_wrong_key(client, registered_agent):
    sub, _, _ = registered_agent
    wrong_key = Ed25519PrivateKey.generate()
    from app.config import settings
    assertion = make_assertion(sub, wrong_key, settings.issuer_url)
    r = client.post("/token", json={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "audience": "test-service",
    })
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_assertion"


def test_token_expired_assertion(client, registered_agent):
    sub, _, key = registered_agent
    from app.config import settings
    assertion = make_assertion(sub, key, settings.issuer_url, ttl=-10)
    r = client.post("/token", json={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "audience": "test-service",
    })
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_assertion"


def test_refresh_token(client, registered_agent):
    sub, _, key = registered_agent
    from app.config import settings
    assertion = make_assertion(sub, key, settings.issuer_url)
    r = client.post("/token", json={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "audience": "test-service",
    })
    refresh_token = r.json()["refresh_token"]

    r2 = client.post("/token/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 200
    data = r2.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token should be different
    assert data["refresh_token"] != refresh_token


def test_refresh_token_single_use(client, registered_agent):
    sub, _, key = registered_agent
    from app.config import settings
    assertion = make_assertion(sub, key, settings.issuer_url)
    r = client.post("/token", json={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "audience": "test-service",
    })
    refresh_token = r.json()["refresh_token"]

    client.post("/token/refresh", json={"refresh_token": refresh_token})
    # Reuse old refresh token should fail
    r3 = client.post("/token/refresh", json={"refresh_token": refresh_token})
    assert r3.status_code == 401
    assert r3.json()["error"] == "invalid_token"


def test_refresh_token_invalid(client):
    r = client.post("/token/refresh", json={"refresh_token": "bogus"})
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_token"
