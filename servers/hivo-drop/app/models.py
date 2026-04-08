from typing import Optional
from pydantic import BaseModel


class FileMetadata(BaseModel):
    path: str
    content_type: str
    visibility: str
    share_id: Optional[str]
    size: int
    sha256: str
    created_at: str
    updated_at: str


class PatchRequest(BaseModel):
    visibility: Optional[str] = None  # "public" | "private"


class ListEntry(BaseModel):
    path: str
    content_type: str
    visibility: str
    share_id: Optional[str]
    size: int
    updated_at: str
