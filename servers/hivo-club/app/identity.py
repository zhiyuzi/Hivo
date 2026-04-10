"""Identity service client for hivo-club — resolve sub -> handle."""
import httpx

from .config import settings

TIMEOUT = 5

# Simple in-memory cache: sub -> handle (str) or None
_handle_cache: dict[str, str | None] = {}


def _identity_base_url() -> str:
    """First trusted issuer is the identity service base URL."""
    issuers = settings.trusted_issuers_list()
    if not issuers:
        return ""
    return issuers[0].rstrip("/")


def resolve_handle(sub: str) -> str | None:
    """Resolve a sub to its handle via identity service. Returns None on failure."""
    if sub in _handle_cache:
        return _handle_cache[sub]

    base = _identity_base_url()
    if not base:
        return None

    try:
        r = httpx.get(f"{base}/resolve", params={"sub": sub}, timeout=TIMEOUT)
        if r.status_code == 200:
            handle = r.json().get("handle")
            _handle_cache[sub] = handle
            return handle
    except Exception:
        pass

    _handle_cache[sub] = None
    return None


def resolve_handles(subs: list[str]) -> dict[str, str | None]:
    """Resolve multiple subs to handles. Returns {sub: handle_or_None}."""
    return {sub: resolve_handle(sub) for sub in subs}
