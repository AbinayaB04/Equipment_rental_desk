"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health
from app.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Equipment Rental Desk API", version="0.0.0")
    # Only GET is needed in M0; methods and headers are widened in M3 with the real endpoints.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET"],
        allow_headers=[],
    )
    app.include_router(health.router)
    return app


app = create_app()
