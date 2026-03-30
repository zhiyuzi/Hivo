from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from .settings import settings

router = APIRouter()

_INDEX_MD = """\
# Hivo

Open infrastructure for agents.

Microservices: hivo-identity, hivo-drop
Skills: {repo_url}/tree/main/skills/

To get started, clone the repository and load the skill for the service you need.
Each skill reads its service endpoint from assets/config.json — update that file for private deployments.
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
