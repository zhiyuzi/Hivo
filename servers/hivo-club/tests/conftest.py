"""
Shared fixtures for hivo-club tests.

Strategy:
- Patch app.auth.get_jwks to return a real Ed25519 test key (no HTTP)
- Patch app.acl functions with in-memory ACL store
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


# ── In-memory ACL ─────────────────────────────────────────────────────────────

class FakeACL:
    """Simulates hivo-acl grant/check/revoke in memory for club file tests."""

    def __init__(self):
        # set of (subject, resource, action, effect)
        self.grants: set[tuple[str, str, str, str]] = set()

    def grant_club_access(self, token: str, club_id: str, file_id: str, permissions: list[str]) -> None:
        resource = f"drop:file:{file_id}"
        for action in permissions:
            self.grants.add((club_id, resource, action, "allow"))

    def revoke_club_access(self, token: str, club_id: str, file_id: str) -> None:
        resource = f"drop:file:{file_id}"
        self.grants = {g for g in self.grants if not (g[0] == club_id and g[1] == resource)}

    def check_file_permission(self, token: str, sub: str, file_id: str, action: str) -> bool:
        resource = f"drop:file:{file_id}"
        if (sub, resource, action, "deny") in self.grants:
            return False
        return (sub, resource, action, "allow") in self.grants

    def add_grant(self, sub: str, file_id: str, action: str, effect: str = "allow") -> None:
        """Test helper to manually add a grant."""
        self.grants.add((sub, f"drop:file:{file_id}", action, effect))


# ── Fake Identity ────────────────────────────────────────────────────────────

# Map sub -> handle for test purposes
_FAKE_HANDLES: dict[str, str] = {
    SUB: "testbot@hivo",
}


def fake_resolve_handle(sub: str) -> str | None:
    return _FAKE_HANDLES.get(sub)


def fake_resolve_handles(subs: list[str]) -> dict[str, str | None]:
    return {sub: _FAKE_HANDLES.get(sub) for sub in subs}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path):
    db_path = str(tmp_path / "club.db")
    fake_acl = FakeACL()

    with mock.patch("app.auth.get_jwks", return_value=[JWK_PUB]), \
         mock.patch("app.auth.settings") as auth_settings, \
         mock.patch("app.db.settings") as db_settings, \
         mock.patch("app.routes.grant_club_access", side_effect=fake_acl.grant_club_access), \
         mock.patch("app.routes.revoke_club_access", side_effect=fake_acl.revoke_club_access), \
         mock.patch("app.routes.check_file_permission", side_effect=fake_acl.check_file_permission), \
         mock.patch("app.routes.resolve_handle", side_effect=fake_resolve_handle), \
         mock.patch("app.routes.resolve_handles", side_effect=fake_resolve_handles):

        auth_settings.trusted_issuers_list.return_value = [ISSUER]
        auth_settings.trusted_issuers = ISSUER
        db_settings.database_path = db_path

        from app.db import init_db
        from app.main import create_app
        init_db(db_path)
        app = create_app()

        with TestClient(app, raise_server_exceptions=True) as c:
            c._fake_acl = fake_acl
            yield c
