"""Pydantic request and response schemas for Members."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.member import MemberStatus
from app.schemas.common import OptionalSingleLineText, SingleLineText
from app.schemas.loan import LoanResponse
from app.schemas.payment import PaymentResponse


class MemberCreate(BaseModel):
    name: SingleLineText = Field(
        ..., min_length=1, max_length=255, description="Full name of member"
    )
    phone: SingleLineText = Field(
        ..., min_length=1, max_length=64, description="Contact phone number"
    )

    model_config = ConfigDict(extra="forbid")


class MemberUpdate(BaseModel):
    name: OptionalSingleLineText = Field(
        default=None, min_length=1, max_length=255, description="Updated name"
    )
    phone: OptionalSingleLineText = Field(
        default=None, min_length=1, max_length=64, description="Updated phone"
    )

    model_config = ConfigDict(extra="forbid")


class MemberResponse(BaseModel):
    id: int
    name: str
    phone: str
    join_date: datetime
    status: MemberStatus
    running_fee_balance: int

    model_config = ConfigDict(from_attributes=True)


class MemberStatementResponse(BaseModel):
    member_id: int
    member: MemberResponse
    loans: list[LoanResponse]
    payments: list[PaymentResponse]
    total_fees_charged: int
    total_payments_recorded: int
    current_outstanding_balance: int

    model_config = ConfigDict(from_attributes=True)
