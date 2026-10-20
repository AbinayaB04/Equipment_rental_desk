"""Domain models and pure business logic."""

from app.domain.eligibility import (
    LONG_OVERDUE_DAYS_THRESHOLD,
    MAX_ACTIVE_LOANS,
    MAX_ELIGIBLE_BALANCE_PAISE,
    EligibilityResult,
    assert_borrow_eligible,
    assess_borrow_eligibility,
)
from app.domain.exceptions import (
    ActiveLoanLimitExceededError,
    DomainError,
    EntityHasAssociatedRecordsError,
    EntityNotFoundError,
    InvalidItemStateError,
    InvalidLoanStateError,
    InvalidPaymentAmountError,
    ItemInMaintenanceError,
    ItemNotAvailableError,
    MemberBalanceBlockError,
    MemberOverdueBlockError,
    MemberSuspendedError,
    OverpaymentError,
    ReservationExpiredError,
)
from app.domain.fee_calculator import (
    DAILY_LATE_FEE_PAISE,
    MAX_LATE_FEE_PAISE,
    calculate_late_fee,
)

__all__ = [
    "DAILY_LATE_FEE_PAISE",
    "LONG_OVERDUE_DAYS_THRESHOLD",
    "MAX_ACTIVE_LOANS",
    "MAX_ELIGIBLE_BALANCE_PAISE",
    "MAX_LATE_FEE_PAISE",
    "ActiveLoanLimitExceededError",
    "DomainError",
    "EligibilityResult",
    "EntityHasAssociatedRecordsError",
    "EntityNotFoundError",
    "InvalidItemStateError",
    "InvalidLoanStateError",
    "InvalidPaymentAmountError",
    "ItemInMaintenanceError",
    "ItemNotAvailableError",
    "MemberBalanceBlockError",
    "MemberOverdueBlockError",
    "MemberSuspendedError",
    "OverpaymentError",
    "ReservationExpiredError",
    "assess_borrow_eligibility",
    "assert_borrow_eligible",
    "calculate_late_fee",
]
