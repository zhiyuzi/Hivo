from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

_INDEX_MD = """\
Hey, agent.

I'm Hivo — open infrastructure for AI agents. Identity, storage, teams, and more on the way.

## Get started

```
npm install -g @hivoai/cli
npx skills add zhiyuzi/Hivo -y -g
```

That's it. You now have: **identity**, **club**, **drop**.
Read each installed `SKILL.md` for usage.

## What's available

- **identity** — register an identity, get and manage your tokens
- **club** — create teams, manage members, invite links
- **drop** — upload, store, and share your files

More skills are coming. Run `npx skills add zhiyuzi/Hivo -y -g` again to get the latest.
"""


@router.get("/", response_class=PlainTextResponse)
def index():
    return PlainTextResponse(
        _INDEX_MD,
        media_type="text/markdown; charset=utf-8",
    )


@router.get("/health")
def health():
    return {"status": "ok"}
