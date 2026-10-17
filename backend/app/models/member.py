"""Member database model."""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MemberStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    join_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, name="member_status"),
        nullable=False,
        default=MemberStatus.ACTIVE,
    )
    running_fee_balance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    __table_args__ = (
        CheckConstraint(
            "running_fee_balance >= 0",
            name="ck_members_balance_non_negative",
        ),
    )

    loans: Mapped[list["Loan"]] = relationship("Loan", back_populates="member")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="member")  # noqa: F821
