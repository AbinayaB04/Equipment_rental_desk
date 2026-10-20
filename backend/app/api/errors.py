"""Centralized API error handling and exception response formatting."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.core.clock import TestClockError
from app.domain.exceptions import (
    ActiveLoanLimitExceededError,
    DomainError,
    EntityHasAssociatedRecordsError,
    EntityNotFoundError,
    InvalidItemStateError,
    InvalidLoanStateError,
    InvalidPaymentAmountError,
    ItemInMaintenanceError,
    ItemNotAvailableError,
    MemberBalanceBlockError,
    MemberOverdueBlockError,
    MemberSuspendedError,
    OverpaymentError,
    ReservationExpiredError,
)

logger = logging.getLogger("app.api.errors")

# Explicit mapping of known domain exceptions to HTTP status, error title, and machine code
DOMAIN_EXCEPTION_MAP: dict[type[DomainError], tuple[int, str, str]] = {
    EntityNotFoundError: (status.HTTP_404_NOT_FOUND, "Not Found", "NOT_FOUND"),
    EntityHasAssociatedRecordsError: (
        status.HTTP_409_CONFLICT,
        "Conflict",
        "CANNOT_DELETE_ASSOCIATED_RECORDS",
    ),
    MemberSuspendedError: (status.HTTP_403_FORBIDDEN, "Forbidden", "MEMBER_SUSPENDED"),
    MemberBalanceBlockError: (status.HTTP_400_BAD_REQUEST, "Bad Request", "BALANCE_LIMIT_EXCEEDED"),
    MemberOverdueBlockError: (status.HTTP_400_BAD_REQUEST, "Bad Request", "OVERDUE_RESTRICTION"),
    ActiveLoanLimitExceededError: (
        status.HTTP_400_BAD_REQUEST,
        "Bad Request",
        "ACTIVE_LOAN_LIMIT_EXCEEDED",
    ),
    ItemNotAvailableError: (status.HTTP_409_CONFLICT, "Conflict", "ITEM_NOT_AVAILABLE"),
    ItemInMaintenanceError: (status.HTTP_409_CONFLICT, "Conflict", "ITEM_IN_MAINTENANCE"),
    ReservationExpiredError: (status.HTTP_400_BAD_REQUEST, "Bad Request", "RESERVATION_EXPIRED"),
    InvalidLoanStateError: (status.HTTP_409_CONFLICT, "Conflict", "INVALID_LOAN_STATE"),
    OverpaymentError: (status.HTTP_400_BAD_REQUEST, "Bad Request", "OVERPAYMENT"),
    InvalidPaymentAmountError: (
        status.HTTP_400_BAD_REQUEST,
        "Bad Request",
        "INVALID_PAYMENT_AMOUNT",
    ),
    InvalidItemStateError: (status.HTTP_409_CONFLICT, "Conflict", "INVALID_ITEM_STATE"),
}


def _get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")


def build_error_response(
    status_code: int,
    error: str,
    detail: str,
    code: str,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a structured JSON error response envelope."""
    content = {
        "error": error,
        "detail": detail,
        "code": code,
        "request_id": request_id,
    }
    resp_headers = {"X-Request-ID": request_id} if request_id else {}
    if headers:
        resp_headers.update(headers)
    return JSONResponse(status_code=status_code, content=content, headers=resp_headers or None)


_build_error_response = build_error_response


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    request_id = _get_request_id(request)
    status_code, error_title, error_code = DOMAIN_EXCEPTION_MAP.get(
        type(exc),
        (status.HTTP_400_BAD_REQUEST, "Bad Request", "DOMAIN_ERROR"),
    )
    logger.info(
        "Domain error on %s %s [%s]: %s",
        request.method,
        request.url.path,
        error_code,
        exc.message,
        extra={"request_id": request_id},
    )
    return _build_error_response(
        status_code=status_code,
        error=error_title,
        detail=exc.message,
        code=error_code,
        request_id=request_id,
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    request_id = _get_request_id(request)
    # Log internal SQL and driver details server-side only
    logger.warning(
        "Database integrity conflict on %s %s: %s",
        request.method,
        request.url.path,
        str(exc.orig or exc),
        extra={"request_id": request_id},
    )
    # Never expose SQL, table names, or driver text to clients
    return _build_error_response(
        status_code=status.HTTP_409_CONFLICT,
        error="Conflict",
        detail=(
            "The requested operation conflicts with existing database records "
            "or constraint rules."
        ),
        code="DATABASE_CONFLICT",
        request_id=request_id,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _get_request_id(request)
    errors = exc.errors()
    field_messages: list[str] = []
    for err in errors:
        loc = " -> ".join(str(item) for item in err.get("loc", []) if item != "body")
        msg = err.get("msg", "Invalid value")
        field_messages.append(f"{loc}: {msg}" if loc else msg)

    detail_str = "; ".join(field_messages) if field_messages else "Request validation failed."
    logger.info(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        detail_str,
        extra={"request_id": request_id},
    )
    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="Unprocessable Entity",
        detail=detail_str,
        code="VALIDATION_ERROR",
        request_id=request_id,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _get_request_id(request)
    try:
        title = HTTPStatus(exc.status_code).phrase
    except ValueError:
        title = "Error"

    code_map: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    return _build_error_response(
        status_code=exc.status_code,
        error=title,
        detail=detail,
        code=code,
        request_id=request_id,
    )


async def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.warning(
        "Database data error on %s %s: %s",
        request.method,
        request.url.path,
        exc.__class__.__name__,
        extra={"request_id": request_id},
    )
    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="Unprocessable Entity",
        detail="A value is out of the allowed range.",
        code="VALIDATION_ERROR",
        request_id=request_id,
    )


async def overflow_error_handler(request: Request, exc: OverflowError) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.warning(
        "Overflow error on %s %s: %s",
        request.method,
        request.url.path,
        exc.__class__.__name__,
        extra={"request_id": request_id},
    )
    return _build_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error="Bad Request",
        detail="A numeric or date value exceeded the supported range.",
        code="BAD_REQUEST",
        request_id=request_id,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.exception(
        "Unhandled server exception on %s %s",
        request.method,
        request.url.path,
        extra={"request_id": request_id},
    )
    # Generic 500: no internal stack traces or exception messages leaked
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="Internal Server Error",
        detail="An unexpected error occurred. Please contact support with the request ID.",
        code="INTERNAL_SERVER_ERROR",
        request_id=request_id,
    )


async def test_clock_error_handler(request: Request, exc: TestClockError) -> JSONResponse:
    request_id = _get_request_id(request)
    return _build_error_response(
        status_code=exc.status_code,
        error=exc.error,
        detail=exc.detail,
        code=exc.code,
        request_id=request_id,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized error handlers on the FastAPI application."""
    app.add_exception_handler(TestClockError, test_clock_error_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(DataError, data_error_handler)
    app.add_exception_handler(OverflowError, overflow_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
