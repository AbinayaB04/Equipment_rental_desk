"""Pydantic request and response schemas for Items."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.item import ItemStatus
from app.schemas.common import (
    NoteText,
    OptionalSingleLineText,
    PositivePaise,
    SingleLineText,
    validate_patch_note_text,
)


class ItemCreate(BaseModel):
    name: SingleLineText = Field(..., min_length=1, max_length=255, description="Equipment name")
    category: SingleLineText = Field(
        ..., min_length=1, max_length=100, description="Equipment category"
    )
    replacement_value: PositivePaise = Field(
        ...,
        description="Replacement value in integer paise (> 0, <= 2147483647)",
    )
    condition_note: NoteText = Field(
        default=None,
        max_length=2000,
        description="Optional notes on equipment condition",
    )

    model_config = ConfigDict(extra="forbid")


class ItemUpdate(BaseModel):
    name: OptionalSingleLineText = Field(
        default=None, min_length=1, max_length=255, description="Updated name"
    )
    category: OptionalSingleLineText = Field(
        default=None, min_length=1, max_length=100, description="Updated category"
    )
    replacement_value: PositivePaise | None = Field(
        default=None,
        description="Updated replacement value in integer paise (> 0, <= 2147483647)",
    )
    condition_note: str | None = Field(
        default=None,
        max_length=2000,
        description="Updated condition notes",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("condition_note", mode="after")
    @classmethod
    def validate_patch_condition_note(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_patch_note_text(v)


class ItemResponse(BaseModel):
    id: int
    name: str
    category: str
    replacement_value: int
    condition_note: str | None
    status: ItemStatus

    model_config = ConfigDict(from_attributes=True)
