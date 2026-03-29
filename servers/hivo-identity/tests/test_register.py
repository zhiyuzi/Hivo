"""Tests for /register and /register/verify."""
import base64
import json
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .conftest import make_jwk


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def do_register(client, handle: str, private_key: Ed25519PrivateKey):
    """Full registration flow. Returns (sub, handle)."""
    jwk = make_jwk(private_key)
    r = client.post("/register", json={"handle": handle, "jwk_pub": jwk})
    assert r.status_code == 201
    challenge = r.json()["challenge"]
    sig = _b64url_encode(private_key.sign(challenge.encode()))
    r2 = client.post("/register/verify", json={"challenge": challenge, "signature": sig})
    assert r2.status_code == 201
    return r2.json()["sub"], handle


def test_register_success(client, agent_key):
    sub, handle = do_register(client, "mybot@corp", agent_key)
    assert sub.startswith("agt_")
    assert handle == "mybot@corp"


def test_register_duplicate_handle(client, agent_key):
    do_register(client, "dupbot@corp", agent_key)
    key2 = Ed25519PrivateKey.generate()
    r = client.post("/register", json={"handle": "dupbot@corp", "jwk_pub": make_jwk(key2)})
    assert r.status_code == 409
    assert r.json()["error"] == "handle_taken"


def test_register_invalid_handle_format(client, agent_key):
    bad_handles = ["no_at_sign", "a@b", "@foo", "foo@", "with space@corp", "ok@corp!"]
    for h in bad_handles:
        r = client.post("/register", json={"handle": h, "jwk_pub": make_jwk(agent_key)})
        assert r.status_code == 422, f"Expected 422 for handle={h!r}, got {r.status_code}"


def test_register_invalid_jwk(client):
    r = client.post("/register", json={
        "handle": "bot@corp",
        "jwk_pub": {"kty": "RSA", "n": "abc", "e": "AQAB"}
    })
    assert r.status_code == 422


def test_verify_wrong_signature(client, agent_key):
    jwk = make_jwk(agent_key)
    r = client.post("/register", json={"handle": "bot@corp", "jwk_pub": jwk})
    assert r.status_code == 201
    challenge = r.json()["challenge"]

    other_key = Ed25519PrivateKey.generate()
    sig = _b64url_encode(other_key.sign(challenge.encode()))
    r2 = client.post("/register/verify", json={"challenge": challenge, "signature": sig})
    assert r2.status_code == 400
    assert r2.json()["error"] == "challenge_failed"


def test_verify_invalid_challenge(client, agent_key):
    r = client.post("/register/verify", json={
        "challenge": "nonexistent_challenge",
        "signature": _b64url_encode(agent_key.sign(b"nonexistent_challenge")),
    })
    assert r.status_code == 400
    assert r.json()["error"] in ("challenge_expired",)


def test_verify_challenge_consumed(client, agent_key):
    """Challenge should be single-use."""
    jwk = make_jwk(agent_key)
    r = client.post("/register", json={"handle": "bot@corp", "jwk_pub": jwk})
    challenge = r.json()["challenge"]
    sig = _b64url_encode(agent_key.sign(challenge.encode()))

    r2 = client.post("/register/verify", json={"challenge": challenge, "signature": sig})
    assert r2.status_code == 201

    # Reuse should fail
    r3 = client.post("/register/verify", json={"challenge": challenge, "signature": sig})
    assert r3.status_code == 400
