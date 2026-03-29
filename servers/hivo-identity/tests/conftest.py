"""Shared fixtures for agent-identity tests."""
import base64
import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.main import create_app
from app.db import init_db
from app.keys import ensure_signing_key, generate_signing_key
from app.config import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwk(private_key: Ed25519PrivateKey) -> dict:
    pub_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {"kty": "OKP", "crv": "Ed25519", "x": _b64url_encode(pub_bytes)}


@pytest.fixture(scope="function")
def tmp_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_identity.db")
    monkeypatch.setattr(settings, "database_path", db_file)
    init_db(db_file)
    ensure_signing_key(db_file)
    return db_file


@pytest.fixture(scope="function")
def client(tmp_db):
    app = create_app()
    # Override startup to avoid reinitializing DB
    app.router.on_startup.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def agent_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture
def registered_agent(client, agent_key):
    """Register an agent and return (sub, handle, private_key)."""
    jwk = make_jwk(agent_key)
    handle = "testbot@acme"

    r = client.post("/register", json={"handle": handle, "jwk_pub": jwk})
    assert r.status_code == 201
    challenge = r.json()["challenge"]

    sig = agent_key.sign(challenge.encode())
    sig_b64 = _b64url_encode(sig)

    r2 = client.post("/register/verify", json={"challenge": challenge, "signature": sig_b64})
    assert r2.status_code == 201
    data = r2.json()
    return data["sub"], handle, agent_key
