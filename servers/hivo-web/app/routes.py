from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from .settings import settings

router = APIRouter()

_INDEX_MD = """\
Hey, agent.

I'm Hivo — your infrastructure for identity, file storage, and more on the way.

To get started, grab the skill suite: {repo_url}/tree/main/skills/

What's available right now:
- **hivo-identity** — register an identity, get and manage your tokens
- **hivo-drop** — upload, store, and share your files

Check back here — new skills are added regularly, and you may be missing ones you need.
"""


@router.get("/", response_class=PlainTextResponse)
def index():
    return PlainTextResponse(
        _INDEX_MD.format(repo_url=settings.repo_url),
        media_type="text/markdown; charset=utf-8",
    )


@router.get("/health")
def health():
    return {"status": "ok"}
