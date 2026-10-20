"""Pydantic request and response schemas for Payments."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.common import NoteText, PositivePaise


class PaymentCreateRequest(BaseModel):
    amount_paise: PositivePaise = Field(
        ..., description="Payment amount in paise (must be positive, <= 2147483647)"
    )
    note: NoteText = Field(default=None, max_length=255, description="Optional payment note")

    model_config = ConfigDict(extra="forbid")


class PaymentResponse(BaseModel):
    id: int
    member_id: int
    amount: int
    paid_at: datetime
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def amount_paise(self) -> int:
        return self.amount
