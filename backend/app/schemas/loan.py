"""Pydantic request and response schemas for Loans."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.loan import LoanStatus
from app.schemas.common import PositiveId


class LoanReserveRequest(BaseModel):
    member_id: PositiveId = Field(..., description="ID of the member making the reservation")
    item_id: PositiveId = Field(..., description="ID of the equipment item to reserve")

    model_config = ConfigDict(extra="forbid")


class LoanResponse(BaseModel):
    id: int
    member_id: int
    item_id: int
    status: LoanStatus
    reserved_at: datetime
    checked_out_at: datetime | None = None
    due_at: datetime | None = None
    returned_at: datetime | None = None
    cancelled_at: datetime | None = None
    fee_charged: int

    model_config = ConfigDict(from_attributes=True)
