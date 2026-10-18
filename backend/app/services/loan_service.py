from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import ensure_utc
from app.domain.exceptions import (
    EntityNotFoundError,
    InvalidLoanStateError,
    ItemInMaintenanceError,
    ItemNotAvailableError,
    ReservationExpiredError,
)
from app.domain.fee_calculator import calculate_late_fee
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member
from app.services.member_service import MemberService

RESERVATION_DURATION = timedelta(hours=48)
LOAN_DURATION = timedelta(days=7)


@dataclass(frozen=True)
class CheckoutOutcome:
    """Outcome of a checkout operation.

    Allows callers managing transactions to inspect whether a checkout succeeded or was
    rejected due to reservation expiry, while safely committing the expiry cleanup without
    an exception rolling back the transaction.
    """

    loan: Loan
    success: bool
    is_expired: bool = False
    rejection_reason: str | None = None


class LoanService:
    """Service handling the complete equipment loan lifecycle with pessimistic locking."""

    @staticmethod
    def get_loan(session: Session, loan_id: int) -> Loan:
        """Retrieve a loan by ID or raise EntityNotFoundError."""
        loan = session.get(Loan, loan_id)
        if loan is None:
            raise EntityNotFoundError(f"Loan with ID {loan_id} not found.")
        return loan

    @staticmethod
    def is_overdue(loan: Loan, now: datetime | None = None) -> bool:
        """Derive whether a loan is currently overdue without stored column or background cron."""
        current_time = ensure_utc(now) or datetime.now(UTC)
        loan_due = ensure_utc(loan.due_at)
        return (
            loan.status == LoanStatus.CHECKED_OUT
            and loan_due is not None
            and current_time > loan_due
        )

    @classmethod
    def get_overdue_loans(
        cls,
        session: Session,
        now: datetime | None = None,
        member_id: int | None = None,
        item_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Loan]:
        """Query currently overdue loans dynamically based on due_at.

        Supports optional member/item filters and pagination.
        """
        current_time = ensure_utc(now) or datetime.now(UTC)
        query = session.query(Loan).filter(
            Loan.status == LoanStatus.CHECKED_OUT,
            Loan.due_at.is_not(None),
            Loan.due_at < current_time,
        )
        if member_id is not None:
            query = query.filter(Loan.member_id == member_id)
        if item_id is not None:
            query = query.filter(Loan.item_id == item_id)
        return query.order_by(Loan.due_at.asc(), Loan.id.asc()).offset(offset).limit(limit).all()

    @classmethod
    def reserve(
        cls,
        session: Session,
        member_id: int,
        item_id: int,
        now: datetime | None = None,
    ) -> Loan:
        """Create a reservation for an equipment item.

        Rules:
        - Locks item and member rows to prevent concurrent duplicate reservations.
        - Member must be eligible to borrow (active, balance <= ₹100, no overdue > 14d,
          and < 3 active loans).
        - Item must not be under maintenance.
        - Item must be available (or have an expired reservation that can be lazily cancelled).
        - Sets item status to RESERVED.
        - Reservation duration is exactly 48 hours.
        """
        current_time = ensure_utc(now) or datetime.now(UTC)

        # Lock item row first
        item = session.query(Item).filter(Item.id == item_id).with_for_update().one_or_none()
        if item is None:
            raise EntityNotFoundError(f"Item with ID {item_id} not found.")

        if item.status == ItemStatus.UNDER_MAINTENANCE:
            raise ItemInMaintenanceError(
                f"Item '{item.name}' cannot be reserved because it is under maintenance."
            )

        if item.status == ItemStatus.CHECKED_OUT:
            raise ItemNotAvailableError(
                f"Item '{item.name}' cannot be reserved because it is currently checked out."
            )

        if item.status == ItemStatus.RESERVED:
            # Check if active reservation is expired
            existing_res = (
                session.query(Loan)
                .filter(Loan.item_id == item_id, Loan.status == LoanStatus.RESERVED)
                .with_for_update()
                .first()
            )
            if existing_res:
                existing_res_at = ensure_utc(existing_res.reserved_at)
                if (
                    existing_res_at is not None
                    and current_time < existing_res_at + RESERVATION_DURATION
                ):
                    raise ItemNotAvailableError(
                        f"Item '{item.name}' is already reserved until "
                        f"{existing_res_at + RESERVATION_DURATION}."
                    )
                # Expired reservation: lazily cancel it
                existing_res.status = LoanStatus.CANCELLED
                existing_res.cancelled_at = current_time

        # Lock member row and verify borrowing eligibility
        member = (
            session.query(Member).filter(Member.id == member_id).with_for_update().one_or_none()
        )
        if member is None:
            raise EntityNotFoundError(f"Member with ID {member_id} not found.")

        MemberService.assert_eligible(session, member_id, now=current_time)

        # Create new reservation
        item.status = ItemStatus.RESERVED
        loan = Loan(
            member_id=member_id,
            item_id=item_id,
            status=LoanStatus.RESERVED,
            reserved_at=current_time,
            fee_charged=0,
        )
        session.add(loan)
        session.flush()
        return loan

    @classmethod
    def settle_expired_reservation(
        cls,
        session: Session,
        loan_id: int,
        now: datetime | None = None,
    ) -> tuple[Loan, bool]:
        """Settle an expired reservation, transitioning loan to CANCELLED and item to AVAILABLE.

        Returns (loan, was_expired):
        - If loan is RESERVED and >= 48 hours old: acquires row locks on loan and item,
          transitions loan to CANCELLED, item to AVAILABLE (if currently RESERVED), flushes,
          and returns (loan, True).
        - If loan is not RESERVED or not yet expired: returns (loan, False) without modifying.
        """
        current_time = ensure_utc(now) or datetime.now(UTC)

        loan = session.query(Loan).filter(Loan.id == loan_id).with_for_update().one_or_none()
        if loan is None:
            raise EntityNotFoundError(f"Loan with ID {loan_id} not found.")

        if loan.status != LoanStatus.RESERVED:
            return loan, False

        loan_reserved_at = ensure_utc(loan.reserved_at)
        if loan_reserved_at is not None and current_time >= loan_reserved_at + RESERVATION_DURATION:
            loan.status = LoanStatus.CANCELLED
            loan.cancelled_at = current_time

            item = (
                session.query(Item).filter(Item.id == loan.item_id).with_for_update().one_or_none()
            )
            if item and item.status == ItemStatus.RESERVED:
                item.status = ItemStatus.AVAILABLE

            session.flush()
            return loan, True

        return loan, False

    @classmethod
    def checkout_with_outcome(
        cls,
        session: Session,
        loan_id: int,
        now: datetime | None = None,
    ) -> CheckoutOutcome:
        """Check out an equipment item, returning CheckoutOutcome for single-transaction commit.

        Rules:
        - Locks loan and item rows to prevent race conditions / concurrent checkouts.
        - Loan must be in RESERVED state.
        - Monotonic clock guard: checkout time cannot precede reservation time.
        - If reservation is expired (>= 48h): transitions loan to CANCELLED, item to AVAILABLE,
          flushes, and returns CheckoutOutcome with is_expired=True.
          The caller's transaction safely commits these cleanup changes without exception rollback.
        - If item is under maintenance: raises ItemInMaintenanceError.
        - If member is ineligible: raises domain eligibility error.
        - On success: sets loan to CHECKED_OUT, due_at = now + 7 days, item to CHECKED_OUT, flushes,
          and returns CheckoutOutcome(loan=loan, success=True).
        """
        current_time = ensure_utc(now) or datetime.now(UTC)

        loan = session.query(Loan).filter(Loan.id == loan_id).with_for_update().one_or_none()
        if loan is None:
            raise EntityNotFoundError(f"Loan with ID {loan_id} not found.")

        if loan.status != LoanStatus.RESERVED:
            raise InvalidLoanStateError(
                f"Cannot check out loan #{loan_id} because its status is {loan.status.value}, "
                "not RESERVED."
            )

        item = session.query(Item).filter(Item.id == loan.item_id).with_for_update().one_or_none()
        if item is None:
            raise EntityNotFoundError(f"Item with ID {loan.item_id} not found.")

        # Monotonic clock guard: checkout time cannot precede reservation time
        loan_reserved_at = ensure_utc(loan.reserved_at)
        if loan_reserved_at is not None and current_time < loan_reserved_at:
            raise InvalidLoanStateError(
                f"Checkout time ({current_time}) cannot be earlier than reservation time "
                f"({loan_reserved_at})."
            )

        # Check 48-hour reservation expiry boundary
        if loan_reserved_at is not None and current_time >= loan_reserved_at + RESERVATION_DURATION:
            loan.status = LoanStatus.CANCELLED
            loan.cancelled_at = current_time
            if item.status == ItemStatus.RESERVED:
                item.status = ItemStatus.AVAILABLE
            session.flush()
            return CheckoutOutcome(
                loan=loan,
                success=False,
                is_expired=True,
                rejection_reason=(
                    f"Reservation #{loan_id} expired at "
                    f"{loan_reserved_at + RESERVATION_DURATION}."
                ),
            )

        if item.status == ItemStatus.UNDER_MAINTENANCE:
            raise ItemInMaintenanceError(
                f"Item '{item.name}' cannot be checked out because it is under maintenance."
            )

        # Re-check member eligibility (e.g. member wasn't suspended or racked up balance)
        MemberService.assert_eligible(session, loan.member_id, now=current_time)

        # Transition loan and item
        loan.status = LoanStatus.CHECKED_OUT
        loan.checked_out_at = current_time
        loan.due_at = current_time + LOAN_DURATION
        item.status = ItemStatus.CHECKED_OUT
        session.flush()
        return CheckoutOutcome(loan=loan, success=True)

    @classmethod
    def checkout(
        cls,
        session: Session,
        loan_id: int,
        now: datetime | None = None,
    ) -> Loan:
        """Check out an equipment item for a valid reservation, raising on expiry.

        For callers managing transactions with `with session.begin():` who wish to settle
        the expired reservation upon catching ReservationExpiredError, call
        `LoanService.settle_expired_reservation(session, loan_id)` in a dedicated transaction,
        or use `LoanService.checkout_with_outcome(session, loan_id)` to settle within a
        single transaction.
        """
        outcome = cls.checkout_with_outcome(session, loan_id=loan_id, now=now)
        if not outcome.success and outcome.is_expired:
            raise ReservationExpiredError(outcome.rejection_reason or "Reservation expired.")
        return outcome.loan

    @classmethod
    def return_item(
        cls,
        session: Session,
        loan_id: int,
        now: datetime | None = None,
    ) -> tuple[Loan, int]:
        """Return a checked-out item, calculating any applicable late fees.

        Rules:
        - Locks loan, item, and member rows for transactional integrity.
        - Loan must be in CHECKED_OUT state (returning an available/reserved/returned
          loan is rejected).
        - Calculates late fee (₹10/day rounded up, capped at ₹200 and replacement value).
        - Assesses and adds late fee to member's running_fee_balance.
        - Sets loan status to RETURNED.
        - If item is not UNDER_MAINTENANCE, item status returns to AVAILABLE.
        - Returns (loan, fee_charged).
        """
        current_time = ensure_utc(now) or datetime.now(UTC)

        loan = session.query(Loan).filter(Loan.id == loan_id).with_for_update().one_or_none()
        if loan is None:
            raise EntityNotFoundError(f"Loan with ID {loan_id} not found.")

        if loan.status != LoanStatus.CHECKED_OUT:
            raise InvalidLoanStateError(
                f"Cannot return loan #{loan_id} because its status is {loan.status.value}, "
                "not CHECKED_OUT."
            )

        item = session.query(Item).filter(Item.id == loan.item_id).with_for_update().one_or_none()
        if item is None:
            raise EntityNotFoundError(f"Item with ID {loan.item_id} not found.")

        member = (
            session.query(Member)
            .filter(Member.id == loan.member_id)
            .with_for_update()
            .one_or_none()
        )
        if member is None:
            raise EntityNotFoundError(f"Member with ID {loan.member_id} not found.")

        # Monotonic clock guard: return time cannot precede check-out time
        loan_checked_out_at = ensure_utc(loan.checked_out_at)
        if loan_checked_out_at is not None and current_time < loan_checked_out_at:
            raise InvalidLoanStateError(
                f"Return time ({current_time}) cannot be earlier than check-out time "
                f"({loan_checked_out_at})."
            )

        # Calculate late fee
        fee_charged = 0
        loan_due_at = ensure_utc(loan.due_at)
        if loan_due_at is not None:
            fee_charged = calculate_late_fee(
                return_time=current_time,
                due_at=loan_due_at,
                replacement_value=item.replacement_value,
            )

        # Update loan record
        loan.status = LoanStatus.RETURNED
        loan.returned_at = current_time
        loan.fee_charged = fee_charged

        # Add late fee to member running balance
        member.running_fee_balance += fee_charged

        # If item was placed in maintenance while checked out, keep it in maintenance
        if item.status != ItemStatus.UNDER_MAINTENANCE:
            item.status = ItemStatus.AVAILABLE

        session.flush()
        return loan, fee_charged

    @classmethod
    def cancel_reservation(
        cls,
        session: Session,
        loan_id: int,
        now: datetime | None = None,
    ) -> Loan:
        """Cancel a pending reservation.

        Rules:
        - Locks loan and item rows.
        - Loan must be in RESERVED state.
        - Sets loan status to CANCELLED and item status to AVAILABLE (if not under maintenance).
        """
        current_time = ensure_utc(now) or datetime.now(UTC)

        loan = session.query(Loan).filter(Loan.id == loan_id).with_for_update().one_or_none()
        if loan is None:
            raise EntityNotFoundError(f"Loan with ID {loan_id} not found.")

        if loan.status != LoanStatus.RESERVED:
            raise InvalidLoanStateError(
                f"Cannot cancel loan #{loan_id} because its status is {loan.status.value}, "
                "not RESERVED."
            )

        # Monotonic clock guard: cancellation time cannot precede reservation time
        loan_reserved_at = ensure_utc(loan.reserved_at)
        if loan_reserved_at is not None and current_time < loan_reserved_at:
            raise InvalidLoanStateError(
                f"Cancellation time ({current_time}) cannot be earlier than reservation time "
                f"({loan_reserved_at})."
            )

        item = session.query(Item).filter(Item.id == loan.item_id).with_for_update().one_or_none()
        if item is None:
            raise EntityNotFoundError(f"Item with ID {loan.item_id} not found.")

        loan.status = LoanStatus.CANCELLED
        loan.cancelled_at = current_time

        if item.status == ItemStatus.RESERVED:
            item.status = ItemStatus.AVAILABLE

        session.flush()
        return loan

    @classmethod
    def list_loans(
        cls,
        session: Session,
        member_id: int | None = None,
        item_id: int | None = None,
        status: LoanStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Loan]:
        """List loans with optional member/item/status filters and pagination."""
        query = session.query(Loan)
        if member_id is not None:
            query = query.filter(Loan.member_id == member_id)
        if item_id is not None:
            query = query.filter(Loan.item_id == item_id)
        if status is not None:
            query = query.filter(Loan.status == status)
        return query.order_by(Loan.id.asc()).offset(offset).limit(limit).all()
