"""Member application service handling eligibility, payments, and account status."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import ensure_utc
from app.domain.eligibility import (
    EligibilityResult,
    assert_borrow_eligible,
    assess_borrow_eligibility,
)
from app.domain.exceptions import (
    EntityNotFoundError,
    InvalidPaymentAmountError,
    OverpaymentError,
)
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus
from app.models.payment import Payment

RESERVATION_DURATION = timedelta(hours=48)


class MemberService:
    """Service handling member eligibility, status transitions, and payments."""

    @staticmethod
    def get_member(session: Session, member_id: int) -> Member:
        """Retrieve a member by ID or raise EntityNotFoundError."""
        member = session.get(Member, member_id)
        if member is None:
            raise EntityNotFoundError(f"Member with ID {member_id} not found.")
        return member

    @staticmethod
    def get_active_loans(
        session: Session,
        member_id: int,
        now: datetime | None = None,
    ) -> list[Loan]:
        """Retrieve currently active loans for a member.

        Active loans include active (non-expired) RESERVED loans and CHECKED_OUT loans.
        Reservations >= 48 hours old are treated as expired and do not count toward
        the active loan limit.
        """
        current_time = now or datetime.now(UTC)
        candidates = (
            session.query(Loan)
            .filter(
                Loan.member_id == member_id,
                Loan.status.in_([LoanStatus.RESERVED, LoanStatus.CHECKED_OUT]),
            )
            .all()
        )

        active: list[Loan] = []
        for loan in candidates:
            reserved_at = ensure_utc(loan.reserved_at)
            if (
                loan.status == LoanStatus.RESERVED
                and reserved_at is not None
                and current_time >= reserved_at + RESERVATION_DURATION
            ):
                # Expired reservation: does not count as active
                continue
            active.append(loan)

        return active

    @classmethod
    def check_eligibility(
        cls,
        session: Session,
        member_id: int,
        now: datetime | None = None,
    ) -> EligibilityResult:
        """Check borrowing eligibility for a member."""
        member = cls.get_member(session, member_id)
        active_loans = cls.get_active_loans(session, member_id, now=now)
        return assess_borrow_eligibility(member, active_loans, now=now)

    @classmethod
    def assert_eligible(
        cls,
        session: Session,
        member_id: int,
        now: datetime | None = None,
    ) -> None:
        """Assert that a member is eligible to borrow, raising domain exceptions if not."""
        member = cls.get_member(session, member_id)
        active_loans = cls.get_active_loans(session, member_id, now=now)
        assert_borrow_eligible(member, active_loans, now=now)

    @classmethod
    def suspend_member(cls, session: Session, member_id: int) -> Member:
        """Suspend a member, blocking borrowing operations."""
        member = cls.get_member(session, member_id)
        member.status = MemberStatus.SUSPENDED
        session.flush()
        return member

    @classmethod
    def reinstate_member(cls, session: Session, member_id: int) -> Member:
        """Reinstate a suspended member to active status."""
        member = cls.get_member(session, member_id)
        member.status = MemberStatus.ACTIVE
        session.flush()
        return member

    @classmethod
    def record_payment(
        cls,
        session: Session,
        member_id: int,
        amount: int,
        note: str | None = None,
        now: datetime | None = None,
    ) -> Payment:
        """Record a fee payment from a member.

        Rules:
        - Amount must be positive (> 0 paise).
        - Amount cannot exceed the member's outstanding running_fee_balance.
        - Reduces running_fee_balance by the paid amount.
        """
        if amount <= 0:
            raise InvalidPaymentAmountError(f"Payment amount must be positive, got {amount} paise.")

        # Lock member row for update to ensure consistent financial deduction
        member = (
            session.query(Member).filter(Member.id == member_id).with_for_update().one_or_none()
        )
        if member is None:
            raise EntityNotFoundError(f"Member with ID {member_id} not found.")

        if amount > member.running_fee_balance:
            max_r = member.running_fee_balance / 100
            pay_r = amount / 100
            raise OverpaymentError(
                f"Payment of ₹{pay_r:.2f} exceeds outstanding balance of ₹{max_r:.2f}."
            )

        member.running_fee_balance -= amount
        payment = Payment(
            member_id=member.id,
            amount=amount,
            paid_at=now or datetime.now(UTC),
            note=note,
        )
        session.add(payment)
        session.flush()
        return payment

    @classmethod
    def list_members(
        cls,
        session: Session,
        status: MemberStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Member]:
        """List members with optional status filter and pagination."""
        query = session.query(Member)
        if status is not None:
            query = query.filter(Member.status == status)
        return query.order_by(Member.id.asc()).offset(offset).limit(limit).all()

    @classmethod
    def create_member(
        cls,
        session: Session,
        name: str,
        phone: str,
        now: datetime | None = None,
    ) -> Member:
        """Create a new member with active status and zero balance."""
        cleaned_name = name.strip()
        cleaned_phone = phone.strip()
        if not cleaned_name:
            raise ValueError("Member name must not be empty.")
        if not cleaned_phone:
            raise ValueError("Member phone must not be empty.")

        current_time = now or datetime.now(UTC)
        member = Member(
            name=cleaned_name,
            phone=cleaned_phone,
            join_date=current_time,
            status=MemberStatus.ACTIVE,
            running_fee_balance=0,
        )
        session.add(member)
        session.flush()
        return member

    @classmethod
    def update_member(
        cls,
        session: Session,
        member_id: int,
        name: str | None = None,
        phone: str | None = None,
    ) -> Member:
        """Update permitted profile fields (name, phone) of an existing member."""
        member = cls.get_member(session, member_id)
        if name is not None:
            cleaned_name = name.strip()
            if not cleaned_name:
                raise ValueError("Member name must not be empty.")
            member.name = cleaned_name
        if phone is not None:
            cleaned_phone = phone.strip()
            if not cleaned_phone:
                raise ValueError("Member phone must not be empty.")
            member.phone = cleaned_phone
        session.flush()
        return member

    @classmethod
    def get_statement(
        cls,
        session: Session,
        member_id: int,
    ) -> dict[str, Any]:
        """Retrieve account statement for a member.

        Includes:
        - Member details
        - All loans (historical, active, overdue, returned, cancelled), ordered newest first
        - All payments, ordered newest first
        - Total late fees charged
        - Total payments recorded
        - Current running fee balance
        """
        member = session.get(Member, member_id)
        if member is None:
            raise EntityNotFoundError(f"Member with ID {member_id} not found.")

        loans = (
            session.query(Loan)
            .filter(Loan.member_id == member_id)
            .order_by(Loan.reserved_at.desc(), Loan.id.desc())
            .all()
        )
        payments = (
            session.query(Payment)
            .filter(Payment.member_id == member_id)
            .order_by(Payment.paid_at.desc(), Payment.id.desc())
            .all()
        )

        total_fees_charged = sum(loan.fee_charged for loan in loans)
        total_payments_recorded = sum(payment.amount for payment in payments)

        return {
            "member_id": member.id,
            "member": member,
            "loans": loans,
            "payments": payments,
            "total_fees_charged": total_fees_charged,
            "total_payments_recorded": total_payments_recorded,
            "current_outstanding_balance": member.running_fee_balance,
        }
