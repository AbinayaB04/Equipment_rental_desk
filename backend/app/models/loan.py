"""Loan database model."""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LoanStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    CHECKED_OUT = "CHECKED_OUT"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus, name="loan_status"),
        nullable=False,
        default=LoanStatus.RESERVED,
    )
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fee_charged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "fee_charged >= 0",
            name="ck_loans_fee_charged_non_negative",
        ),
        CheckConstraint(
            "status != 'RESERVED' OR ("
            "checked_out_at IS NULL AND due_at IS NULL AND "
            "returned_at IS NULL AND cancelled_at IS NULL)",
            name="ck_loans_reserved_timestamps",
        ),
        CheckConstraint(
            "status != 'CHECKED_OUT' OR ("
            "checked_out_at IS NOT NULL AND due_at IS NOT NULL AND "
            "due_at > checked_out_at AND returned_at IS NULL AND cancelled_at IS NULL)",
            name="ck_loans_checked_out_timestamps",
        ),
        CheckConstraint(
            "status != 'RETURNED' OR ("
            "checked_out_at IS NOT NULL AND due_at IS NOT NULL AND "
            "returned_at IS NOT NULL AND returned_at >= checked_out_at AND "
            "cancelled_at IS NULL)",
            name="ck_loans_returned_timestamps",
        ),
        CheckConstraint(
            "status != 'CANCELLED' OR ("
            "checked_out_at IS NULL AND due_at IS NULL AND returned_at IS NULL AND "
            "cancelled_at IS NOT NULL AND cancelled_at >= reserved_at)",
            name="ck_loans_cancelled_timestamps",
        ),
    )

    member: Mapped["Member"] = relationship("Member", back_populates="loans")  # noqa: F821
    item: Mapped["Item"] = relationship("Item", back_populates="loans")  # noqa: F821
