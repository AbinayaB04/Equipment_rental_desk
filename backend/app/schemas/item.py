"""Pydantic request and response schemas for Items."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.item import ItemStatus


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Equipment name")
    category: str = Field(..., min_length=1, max_length=100, description="Equipment category")
    replacement_value: int = Field(
        ...,
        gt=0,
        description="Replacement value in integer paise (> 0)",
    )
    condition_note: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional notes on equipment condition",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "category", mode="after")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Must not be empty or whitespace only.")
        return cleaned

    @field_validator("condition_note", mode="after")
    @classmethod
    def normalize_condition_note(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip()


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255, description="Updated name")
    category: str | None = Field(
        default=None, min_length=1, max_length=100, description="Updated category"
    )
    replacement_value: int | None = Field(
        default=None,
        gt=0,
        description="Updated replacement value in integer paise (> 0)",
    )
    condition_note: str | None = Field(
        default=None,
        max_length=2000,
        description="Updated condition notes",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "category", mode="after")
    @classmethod
    def validate_optional_non_empty_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Must not be empty or whitespace only.")
        return cleaned

    @field_validator("condition_note", mode="after")
    @classmethod
    def normalize_condition_note(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip()


class ItemResponse(BaseModel):
    id: int
    name: str
    category: str
    replacement_value: int
    condition_note: str | None
    status: ItemStatus

    model_config = ConfigDict(from_attributes=True)
