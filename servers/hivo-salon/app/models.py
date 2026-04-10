"""Pydantic models for hivo-salon."""
from typing import Optional
from pydantic import BaseModel


# --- Requests ---

class CreateSalonRequest(BaseModel):
    name: str
    club_id: str
    bulletin: Optional[str] = None


class UpdateSalonRequest(BaseModel):
    name: Optional[str] = None
    bulletin: Optional[str] = None


class AddMemberRequest(BaseModel):
    sub: str
    role: str = "member"


class UpdateMemberRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    role: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: list[dict]


class AddFileRequest(BaseModel):
    file_id: str
    alias: str
    permissions: str = "read"


# --- Responses ---

class SalonResponse(BaseModel):
    id: str
    club_id: str
    name: str
    bulletin: Optional[str] = None
    owner_sub: str
    owner_handle: Optional[str] = None
    created_at: str
    updated_at: str


class MemberResponse(BaseModel):
    id: str
    salon_id: str
    sub: str
    handle: Optional[str] = None
    role: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    joined_at: str


class MessageResponse(BaseModel):
    id: str
    salon_id: str
    sender_sub: str
    sender_handle: Optional[str] = None
    content: list[dict]
    created_at: str


class FileResponse(BaseModel):
    id: str
    salon_id: str
    file_id: str
    owner_sub: str
    owner_handle: Optional[str] = None
    alias: str
    permissions: str
    added_at: str


class InboxEntry(BaseModel):
    salon_id: str
    salon_name: str
    club_id: str
    unread_count: int
    has_mention: bool = False
    last_message_at: Optional[str] = None
