"""Common API schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard API error response envelope."""

    error: str
    detail: str
    code: str
    request_id: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated collection response."""

    items: list[T]
    total: int
    limit: int
    offset: int
