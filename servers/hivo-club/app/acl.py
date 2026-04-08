"""ACL service client for hivo-club."""
import httpx
from fastapi import HTTPException

from .config import settings

TIMEOUT = 10


def grant_club_access(token: str, club_id: str, file_id: str, permissions: list[str]) -> None:
    """Grant club access to a Drop file via ACL."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resource = f"drop:file:{file_id}"
    subject = club_id  # already prefixed with "club_"
    try:
        httpx.post(
            f"{settings.acl_url}/grants/batch",
            headers=headers,
            json={"grants": [
                {"subject": subject, "resource": resource, "action": action, "effect": "allow"}
                for action in permissions
            ]},
            timeout=TIMEOUT,
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"error": "acl_error", "message": "Failed to grant club file permissions"},
        )


def revoke_club_access(token: str, club_id: str, file_id: str) -> None:
    """Revoke all of a club's ACL grants on a Drop file."""
    try:
        httpx.request(
            "DELETE",
            f"{settings.acl_url}/grants",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"subject": club_id, "resource": f"drop:file:{file_id}"},
            timeout=TIMEOUT,
        )
    except Exception:
        pass


def check_file_permission(token: str, sub: str, file_id: str, action: str) -> bool:
    """Check if subject has permission on a Drop file via ACL."""
    try:
        r = httpx.get(
            f"{settings.acl_url}/check",
            headers={"Authorization": f"Bearer {token}"},
            params={"subject": sub, "resource": f"drop:file:{file_id}", "action": action},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return False
        return r.json().get("allowed", False)
    except Exception:
        return False
