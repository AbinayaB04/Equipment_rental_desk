"""Pydantic request and response schemas for Members."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.member import MemberStatus
from app.schemas.loan import LoanResponse
from app.schemas.payment import PaymentResponse


class MemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of member")
    phone: str = Field(..., min_length=1, max_length=64, description="Contact phone number")

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "phone", mode="after")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Must not be empty or whitespace only.")
        return cleaned


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255, description="Updated name")
    phone: str | None = Field(
        default=None, min_length=1, max_length=64, description="Updated phone"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "phone", mode="after")
    @classmethod
    def validate_optional_non_empty_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Must not be empty or whitespace only.")
        return cleaned


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
