from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .db import init_db
from .routes import router


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        yield

    app = FastAPI(title="Agent Drop", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(422)
    async def validation_error_handler(request, exc):
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "message": str(exc.errors())},
        )

    return app


app = create_app()
