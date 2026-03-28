"""Service signing key management (Ed25519)."""
import json
import uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

from .db import get_conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_signing_key(db_path: str | None = None) -> str:
    """Generate a new Ed25519 signing key and store it. Returns kid."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    kid = str(uuid.uuid4())
    # Build JWK for public key
    import base64
    x_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()
    jwk_pub = json.dumps({"kty": "OKP", "crv": "Ed25519", "x": x_b64, "kid": kid})

    with get_conn(db_path) as conn:
        conn.execute("UPDATE signing_keys SET is_current = 0")
        conn.execute(
            "INSERT INTO signing_keys (kid, alg, private_key, public_key, is_current, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (kid, "EdDSA", priv_bytes.decode(), jwk_pub, _now_iso()),
        )
    return kid


def get_current_signing_key(db_path: str | None = None) -> tuple[str, Ed25519PrivateKey, dict]:
    """Returns (kid, private_key, jwk_pub_dict)."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT kid, private_key, public_key FROM signing_keys WHERE is_current = 1 LIMIT 1"
        ).fetchone()
    if not row:
        raise RuntimeError("No signing key found. Run init_signing_key() first.")

    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    private_key = load_pem_private_key(row["private_key"].encode(), password=None)
    return row["kid"], private_key, json.loads(row["public_key"])


def get_all_public_keys(db_path: str | None = None) -> list[dict]:
    """Returns list of JWK dicts for all signing keys."""
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT public_key FROM signing_keys").fetchall()
    return [json.loads(r["public_key"]) for r in rows]


def ensure_signing_key(db_path: str | None = None) -> None:
    """Create a signing key if none exists."""
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT kid FROM signing_keys WHERE is_current = 1 LIMIT 1").fetchone()
    if not row:
        generate_signing_key(db_path)
