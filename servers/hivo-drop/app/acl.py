"""ACL service client for hivo-drop."""
import httpx
from fastapi import HTTPException

from .config import settings

TIMEOUT = 10


def register_owner_grants(token: str, sub: str, file_id: str) -> None:
    """Register owner's four permissions in ACL after file upload."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resource = f"drop:file:{file_id}"
    try:
        httpx.post(
            f"{settings.acl_url}/grants/batch",
            headers=headers,
            json={"grants": [
                {"subject": sub, "resource": resource, "action": action, "effect": "allow"}
                for action in ("read", "write", "delete", "admin")
            ]},
            timeout=TIMEOUT,
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"error": "acl_error", "message": "Failed to register file permissions"},
        )


def check_permission(token: str, sub: str, file_id: str, action: str) -> bool:
    """Check if subject has permission on a file via ACL."""
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


def revoke_all_grants(token: str, file_id: str) -> None:
    """Revoke all ACL grants for a file (subject=*)."""
    try:
        httpx.request(
            "DELETE",
            f"{settings.acl_url}/grants",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"subject": "*", "resource": f"drop:file:{file_id}"},
            timeout=TIMEOUT,
        )
    except Exception:
        pass
