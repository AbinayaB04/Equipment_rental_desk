"""Liveness endpoint. A database check is added once the database layer exists (M1)."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    test_clock_enabled: bool


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings: Settings = getattr(request.app.state, "settings", None) or Settings.from_env()
    return HealthResponse(status="ok", test_clock_enabled=settings.allow_test_clock)
