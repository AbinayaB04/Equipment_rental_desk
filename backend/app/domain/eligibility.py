"""Borrowing eligibility rules for tool library members."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.clock import ensure_utc
from app.domain.exceptions import (
    ActiveLoanLimitExceededError,
    MemberBalanceBlockError,
    MemberOverdueBlockError,
    MemberSuspendedError,
)
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus

# Financial and business constants
MAX_ACTIVE_LOANS = 3
MAX_ELIGIBLE_BALANCE_PAISE = 10000  # ₹100 in paise
LONG_OVERDUE_DAYS_THRESHOLD = 14  # > 14 days overdue blocks borrowing


@dataclass(frozen=True)
class EligibilityResult:
    """Detailed eligibility assessment for a member."""

    is_eligible: bool
    reasons: tuple[str, ...]

    @property
    def primary_reason(self) -> str | None:
        return self.reasons[0] if self.reasons else None


def assess_borrow_eligibility(
    member: Member,
    active_loans: list[Loan],
    now: datetime | None = None,
) -> EligibilityResult:
    """Assess whether a member is currently eligible to reserve or borrow equipment.

    Rules:
    1. Member status must be ACTIVE (SUSPENDED members cannot borrow).
    2. Member running_fee_balance must be <= ₹100 (10,000 paise).
    3. No loan may be overdue by more than 14 days (> 14 * 24 hours).
    4. Active loans (RESERVED + CHECKED_OUT) must be < 3.
    """
    check_time = now or datetime.now(UTC)
    reasons: list[str] = []

    # Rule 1: Member suspension
    if member.status != MemberStatus.ACTIVE:
        reasons.append(f"Member '{member.name}' is currently suspended.")

    # Rule 2: Balance limit (> ₹100 blocks)
    if member.running_fee_balance > MAX_ELIGIBLE_BALANCE_PAISE:
        balance_rupees = member.running_fee_balance / 100
        reasons.append(
            f"Outstanding fee balance (₹{balance_rupees:.2f}) exceeds the ₹100.00 limit."
        )

    # Rule 3: Long overdue (> 14 days blocks)
    long_overdue_cutoff = check_time - timedelta(days=LONG_OVERDUE_DAYS_THRESHOLD)
    for loan in active_loans:
        loan_due_at = ensure_utc(loan.due_at)
        if (
            loan.status == LoanStatus.CHECKED_OUT
            and loan_due_at is not None
            and loan_due_at < long_overdue_cutoff
        ):
            reasons.append(
                f"Loan #{loan.id} is overdue by more than {LONG_OVERDUE_DAYS_THRESHOLD} days."
            )
            break

    # Rule 4: Active loan limit (max 3)
    if len(active_loans) >= MAX_ACTIVE_LOANS:
        reasons.append(
            f"Member has reached the limit of {MAX_ACTIVE_LOANS} active loans "
            f"(currently holding {len(active_loans)})."
        )

    return EligibilityResult(
        is_eligible=len(reasons) == 0,
        reasons=tuple(reasons),
    )


def assert_borrow_eligible(
    member: Member,
    active_loans: list[Loan],
    now: datetime | None = None,
) -> None:
    """Assert that a member is eligible to borrow, raising domain exceptions if not."""
    check_time = now or datetime.now(UTC)

    if member.status != MemberStatus.ACTIVE:
        raise MemberSuspendedError(f"Member '{member.name}' is currently suspended.")

    if member.running_fee_balance > MAX_ELIGIBLE_BALANCE_PAISE:
        balance_rupees = member.running_fee_balance / 100
        raise MemberBalanceBlockError(
            f"Outstanding fee balance (₹{balance_rupees:.2f}) exceeds the ₹100.00 limit."
        )

    long_overdue_cutoff = check_time - timedelta(days=LONG_OVERDUE_DAYS_THRESHOLD)
    for loan in active_loans:
        loan_due_at = ensure_utc(loan.due_at)
        if (
            loan.status == LoanStatus.CHECKED_OUT
            and loan_due_at is not None
            and loan_due_at < long_overdue_cutoff
        ):
            raise MemberOverdueBlockError(
                f"Loan #{loan.id} is overdue by more than {LONG_OVERDUE_DAYS_THRESHOLD} days."
            )

    if len(active_loans) >= MAX_ACTIVE_LOANS:
        raise ActiveLoanLimitExceededError(
            f"Member has reached the limit of {MAX_ACTIVE_LOANS} active loans."
        )
