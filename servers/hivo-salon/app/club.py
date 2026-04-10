"""Club service client for hivo-salon — check club membership."""
import httpx

from .config import settings

TIMEOUT = 5


def check_membership(club_id: str, sub: str) -> dict | None:
    """Check if sub is a member of the given club.

    Calls GET {CLUB_URL}/internal/clubs/{club_id}/members/{sub}.
    Returns the membership dict on success, or None if not a member / error.
    """
    base = settings.club_url.rstrip("/")
    try:
        r = httpx.get(
            f"{base}/internal/clubs/{club_id}/members/{sub}",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None
