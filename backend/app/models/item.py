"""Item database model."""

import enum

from sqlalchemy import CheckConstraint, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ItemStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    CHECKED_OUT = "CHECKED_OUT"
    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    replacement_value: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status"),
        nullable=False,
        default=ItemStatus.AVAILABLE,
    )

    __table_args__ = (
        CheckConstraint(
            "replacement_value > 0",
            name="ck_items_replacement_value_positive",
        ),
    )

    loans: Mapped[list["Loan"]] = relationship("Loan", back_populates="item")  # noqa: F821
