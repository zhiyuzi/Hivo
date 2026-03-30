from fastapi import FastAPI

from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Hivo Web", docs_url=None, redoc_url=None)
    app.include_router(router)
    return app


app = create_app()
