"""
Shared fixtures for hivo-club tests.

Strategy:
- Patch app.auth.get_jwks to return a real Ed25519 test key (no HTTP)
- Use a temp SQLite DB for each test
"""
import base64
import json
import unittest.mock as mock
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient


# ── Keypair ────────────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


PRIVATE_KEY: Ed25519PrivateKey = Ed25519PrivateKey.generate()
_pub_raw = PRIVATE_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
KID = "test-kid-001"
JWK_PUB = {"kty": "OKP", "crv": "Ed25519", "x": _b64url(_pub_raw), "kid": KID}
ISSUER = "https://id.test"
SUB = "agt_test_001"


def make_token(
    sub: str = SUB,
    iss: str = ISSUER,
    aud: str = "hivo-club",
    exp_delta: int = 3600,
) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    header = {"alg": "EdDSA", "typ": "JWT", "kid": KID}
    payload = {"iss": iss, "sub": sub, "aud": aud, "iat": now, "exp": now + exp_delta}

    def enc(d):
        return _b64url(json.dumps(d, separators=(",", ":")).encode())

    h, p = enc(header), enc(payload)
    sig = PRIVATE_KEY.sign(f"{h}.{p}".encode())
    return f"{h}.{p}.{_b64url(sig)}"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path):
    db_path = str(tmp_path / "club.db")

    with mock.patch("app.auth.get_jwks", return_value=[JWK_PUB]), \
         mock.patch("app.auth.settings") as auth_settings, \
         mock.patch("app.db.settings") as db_settings:

        auth_settings.trusted_issuers_list.return_value = [ISSUER]
        auth_settings.trusted_issuers = ISSUER
        db_settings.database_path = db_path

        from app.db import init_db
        from app.main import create_app
        init_db(db_path)
        app = create_app()

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
