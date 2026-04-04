from typing import Literal, Optional
from pydantic import BaseModel


class GrantRequest(BaseModel):
    subject: str
    resource: str
    action: Literal["read", "write", "delete", "admin"]
    effect: Literal["allow", "deny"] = "allow"


class RevokeRequest(BaseModel):
    subject: str
    resource: str
    action: Optional[Literal["read", "write", "delete", "admin"]] = None
    effect: Optional[Literal["allow", "deny"]] = None


class GrantResponse(BaseModel):
    subject: str
    resource: str
    action: str
    effect: str
    granted_by: str
    created_at: str


class CheckResponse(BaseModel):
    allowed: bool
