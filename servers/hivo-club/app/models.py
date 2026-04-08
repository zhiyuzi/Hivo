from typing import Optional
from pydantic import BaseModel


# ── Requests ──────────────────────────────────────────────────────────────────

class CreateClubRequest(BaseModel):
    name: str
    description: Optional[str] = None


class AddMemberRequest(BaseModel):
    sub: str
    role: str = "member"


class CreateInviteLinkRequest(BaseModel):
    role: str = "member"
    max_uses: Optional[int] = None
    expires_at: Optional[str] = None


class UpdateRoleRequest(BaseModel):
    role: str


class UpdateClubRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class UpdateMyMembershipRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None


class AddFileRequest(BaseModel):
    file_id: str
    alias: str
    permissions: str = "read"


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
    display_name: Optional[str] = None
    bio: Optional[str] = None
    note: Optional[str] = None
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


class ClubFileResponse(BaseModel):
    id: str
    club_id: str
    file_id: str
    owner_sub: str
    alias: str
    permissions: str
    contributed_by: str
    added_at: str
