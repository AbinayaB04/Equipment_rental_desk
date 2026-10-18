"""Member API routes."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.clock import get_request_clock
from app.core.database import get_db
from app.models.member import MemberStatus
from app.schemas.member import (
    MemberCreate,
    MemberResponse,
    MemberStatementResponse,
    MemberUpdate,
)
from app.schemas.payment import PaymentCreateRequest, PaymentResponse
from app.services.member_service import MemberService

router = APIRouter()


@router.get("", response_model=list[MemberResponse])
def list_members(
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[
        MemberStatus | None,
        Query(alias="status", description="Filter by member status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Max records to return")] = 100,
    offset: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
) -> list[MemberResponse]:
    """List members with optional status filter and pagination."""
    return MemberService.list_members(db, status=status_filter, limit=limit, offset=offset)


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> MemberResponse:
    """Create a new member with active status and zero balance."""
    return MemberService.create_member(db, name=payload.name, phone=payload.phone, now=now)


@router.get("/{member_id}", response_model=MemberResponse)
def get_member(
    member_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> MemberResponse:
    """Retrieve a single member by ID."""
    return MemberService.get_member(db, member_id=member_id)


@router.patch("/{member_id}", response_model=MemberResponse)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> MemberResponse:
    """Update permitted profile fields (name, phone) of a member."""
    return MemberService.update_member(
        db,
        member_id=member_id,
        name=payload.name,
        phone=payload.phone,
    )


@router.post("/{member_id}/suspend", response_model=MemberResponse)
def suspend_member(
    member_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> MemberResponse:
    """Suspend a member, blocking borrowing operations."""
    return MemberService.suspend_member(db, member_id=member_id)


@router.post("/{member_id}/reinstate", response_model=MemberResponse)
def reinstate_member(
    member_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> MemberResponse:
    """Reinstate a suspended member to active status."""
    return MemberService.reinstate_member(db, member_id=member_id)


@router.post("/{member_id}/reactivate", response_model=MemberResponse, include_in_schema=False)
def reactivate_member(
    member_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> MemberResponse:
    """Alias for reinstate_member."""
    return MemberService.reinstate_member(db, member_id=member_id)


@router.post(
    "/{member_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_payment(
    member_id: int,
    payload: PaymentCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> PaymentResponse:
    """Record a fee payment against a member's running fee balance."""
    return MemberService.record_payment(
        db,
        member_id=member_id,
        amount=payload.amount_paise,
        note=payload.note,
        now=now,
    )


@router.get(
    "/{member_id}/statement",
    response_model=MemberStatementResponse,
)
def get_member_statement(
    member_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> Any:
    """Retrieve an itemized statement of loans, payments, and fees for a member."""
    return MemberService.get_statement(db, member_id=member_id)
