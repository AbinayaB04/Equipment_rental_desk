"""Loan API routes handling reservation, checkout, return, cancellation, and retrieval."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.errors import build_error_response
from app.core.clock import get_request_clock
from app.core.database import get_db
from app.models.loan import LoanStatus
from app.schemas.common import (
    OptionalIdQuery,
    PaginationLimit,
    PaginationOffset,
    PositiveId,
)
from app.schemas.loan import LoanReserveRequest, LoanResponse
from app.services.loan_service import LoanService

router = APIRouter()


@router.post("/reserve", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
def reserve_loan(
    payload: LoanReserveRequest,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> LoanResponse:
    """Reserve an equipment item for a member."""
    return LoanService.reserve(
        db,
        member_id=payload.member_id,
        item_id=payload.item_id,
        now=now,
    )


@router.post("/{loan_id}/checkout", response_model=LoanResponse)
def checkout_loan(
    loan_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
    request: Request,
) -> Any:
    """Check out an equipment item for a valid reservation.

    If the reservation has expired, the cancellation is committed to the database
    and an HTTP 400 RESERVATION_EXPIRED error response is returned.
    """
    outcome = LoanService.checkout_with_outcome(db, loan_id=loan_id, now=now)
    if not outcome.success and outcome.is_expired:
        db.commit()
        request_id = getattr(request.state, "request_id", None) or request.headers.get(
            "X-Request-ID"
        )
        return build_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Bad Request",
            detail=outcome.rejection_reason or f"Reservation #{loan_id} expired.",
            code="RESERVATION_EXPIRED",
            request_id=request_id,
        )
    return outcome.loan


@router.post("/{loan_id}/return", response_model=LoanResponse)
def return_loan(
    loan_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> LoanResponse:
    """Return a checked-out equipment item and assess any applicable late fees."""
    loan, _ = LoanService.return_item(db, loan_id=loan_id, now=now)
    return loan


@router.post("/{loan_id}/cancel", response_model=LoanResponse)
def cancel_loan(
    loan_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> LoanResponse:
    """Cancel a pending reservation and restore the item to AVAILABLE."""
    return LoanService.cancel_reservation(db, loan_id=loan_id, now=now)


@router.get("/overdue", response_model=list[LoanResponse])
def list_overdue_loans(
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
    member_id: OptionalIdQuery = None,
    item_id: OptionalIdQuery = None,
    limit: PaginationLimit = 100,
    offset: PaginationOffset = 0,
) -> list[LoanResponse]:
    """List currently overdue loans dynamically based on due_at and current clock."""
    return LoanService.get_overdue_loans(
        db,
        now=now,
        member_id=member_id,
        item_id=item_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{loan_id}", response_model=LoanResponse)
def get_loan(
    loan_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
) -> LoanResponse:
    """Retrieve loan details by loan ID."""
    return LoanService.get_loan(db, loan_id=loan_id)


@router.get("", response_model=list[LoanResponse])
def list_loans(
    db: Annotated[Session, Depends(get_db)],
    member_id: OptionalIdQuery = None,
    item_id: OptionalIdQuery = None,
    status_filter: Annotated[
        LoanStatus | None,
        Query(alias="status", description="Filter by loan status"),
    ] = None,
    limit: PaginationLimit = 100,
    offset: PaginationOffset = 0,
) -> list[LoanResponse]:
    """List loans with optional filters and bounded pagination."""
    return LoanService.list_loans(
        db,
        member_id=member_id,
        item_id=item_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
