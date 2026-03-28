import re
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional

HANDLE_RE = re.compile(r'^[a-zA-Z0-9\-]{2,32}@[a-zA-Z0-9\-]{2,32}$')


def validate_handle(handle: str) -> str:
    if not HANDLE_RE.match(handle):
        raise ValueError(
            "handle must be in format name@namespace, each part 2-32 chars, "
            "only letters, digits, hyphens"
        )
    return handle


class RegisterRequest(BaseModel):
    handle: str
    jwk_pub: dict
    email: Optional[str] = None
    display_name: Optional[str] = None

    @field_validator("handle")
    @classmethod
    def check_handle(cls, v: str) -> str:
        return validate_handle(v)

    @field_validator("jwk_pub")
    @classmethod
    def check_jwk(cls, v: dict) -> dict:
        if v.get("kty") != "OKP" or v.get("crv") != "Ed25519":
            raise ValueError("jwk_pub must be an Ed25519 OKP key")
        if "x" not in v:
            raise ValueError("jwk_pub missing x parameter")
        return v


class RegisterResponse(BaseModel):
    challenge: str


class VerifyRequest(BaseModel):
    challenge: str
    signature: str  # base64url-encoded Ed25519 signature of challenge


class VerifyResponse(BaseModel):
    sub: str
    handle: str


class TokenRequest(BaseModel):
    grant_type: str = "urn:ietf:params:oauth:grant-type:jwt-bearer"
    assertion: str  # private_key_jwt signed by agent

    @field_validator("grant_type")
    @classmethod
    def check_grant(cls, v: str) -> str:
        if v != "urn:ietf:params:oauth:grant-type:jwt-bearer":
            raise ValueError("unsupported grant_type")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    sub: str
    handle: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    status: str
    created_at: str
