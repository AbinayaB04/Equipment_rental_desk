"""Domain exceptions representing business rule violations and domain errors."""


class DomainError(Exception):
    """Base domain exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundError(DomainError):
    """Raised when an entity is not found."""


class MemberSuspendedError(DomainError):
    """Raised when a suspended member attempts a restricted operation."""


class MemberBalanceBlockError(DomainError):
    """Raised when a member has unpaid balance exceeding ₹100."""


class MemberOverdueBlockError(DomainError):
    """Raised when a member has a loan overdue by more than 14 days."""


class ActiveLoanLimitExceededError(DomainError):
    """Raised when a member attempts to exceed the 3 active loans limit."""


class ItemNotAvailableError(DomainError):
    """Raised when an item is not available for reservation or checkout."""


class ItemInMaintenanceError(DomainError):
    """Raised when an item is under maintenance."""


class ReservationExpiredError(DomainError):
    """Raised when attempting to check out an expired reservation."""


class InvalidLoanStateError(DomainError):
    """Raised on invalid loan transition (e.g. double return, returning a reservation)."""


class OverpaymentError(DomainError):
    """Raised when a payment exceeds the member's outstanding balance."""


class InvalidPaymentAmountError(DomainError):
    """Raised when a payment amount is non-positive."""


class InvalidItemStateError(DomainError):
    """Raised when attempting an invalid item state transition."""
