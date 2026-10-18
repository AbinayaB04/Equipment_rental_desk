"""Pydantic request and response schemas for Payments."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class PaymentCreateRequest(BaseModel):
    amount_paise: int = Field(..., gt=0, description="Payment amount in paise (must be positive)")
    note: str | None = Field(default=None, max_length=255, description="Optional payment note")

    model_config = ConfigDict(extra="forbid")

    @field_validator("note", mode="after")
    @classmethod
    def clean_note(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None


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
