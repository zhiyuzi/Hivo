from typing import Optional
from pydantic import BaseModel


# ── Requests ──────────────────────────────────────────────────────────────────

class CreateClubRequest(BaseModel):
    name: str
    description: Optional[str] = None


class InviteMemberRequest(BaseModel):
    sub: Optional[str] = None
    role: str = "member"
    max_uses: Optional[int] = None
    expires_at: Optional[str] = None


class UpdateRoleRequest(BaseModel):
    role: str


# ── Responses ─────────────────────────────────────────────────────────────────

class ClubResponse(BaseModel):
    club_id: str
    name: str
    description: Optional[str]
    owner_sub: str
    created_at: str
    updated_at: str


class MemberResponse(BaseModel):
    sub: str
    role: str
    note: Optional[str]
    invited_by: str
    joined_at: str


class InviteLinkResponse(BaseModel):
    token: str
    club_id: str
    role: str
    max_uses: Optional[int]
    use_count: int
    expires_at: Optional[str]
    created_at: str


class JoinResponse(BaseModel):
    club_id: str
    sub: str
    role: str


class MyClubEntry(BaseModel):
    club_id: str
    name: str
    role: str
    joined_at: str
