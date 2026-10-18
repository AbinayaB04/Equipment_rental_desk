"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routers import health, items, loans, members
from app.core.config import Settings
from app.core.middleware import RequestIdAndLoggingMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Equipment Rental Desk API", version="0.0.0")
    app.state.settings = settings

    # Request ID and structured request logging
    app.add_middleware(RequestIdAndLoggingMiddleware)

    # CORS middleware (widened in M3 for standard REST operations)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Centralized exception handlers for domain, DB integrity, validation, and unexpected errors
    register_exception_handlers(app)

    # Routers
    app.include_router(health.router)
    app.include_router(members.router, prefix="/members", tags=["members"])
    app.include_router(items.router, prefix="/items", tags=["items"])
    app.include_router(loans.router, prefix="/loans", tags=["loans"])
    # Aliases under /api prefix for full client URL compatibility
    app.include_router(
        members.router, prefix="/api/members", tags=["members"], include_in_schema=False
    )
    app.include_router(items.router, prefix="/api/items", tags=["items"], include_in_schema=False)
    app.include_router(loans.router, prefix="/api/loans", tags=["loans"], include_in_schema=False)
    return app


app = create_app()
