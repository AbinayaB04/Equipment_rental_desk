"""Business-rule behavioral test contracts for Milestone 2 (M2).

Implements and validates the complete set of business rules from Problem 1: Equipment Rental Desk
against the domain and service layers.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.exceptions import (
    ActiveLoanLimitExceededError,
    InvalidLoanStateError,
    MemberBalanceBlockError,
    MemberOverdueBlockError,
    MemberSuspendedError,
    ReservationExpiredError,
)
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus
from app.services.fee_service import calculate_late_fee
from app.services.item_service import ItemService
from app.services.loan_service import LoanService
from app.services.member_service import MemberService


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def member(session: Session, now: datetime) -> Member:
    m = Member(
        name="Test Member",
        phone="+91-98765-00001",
        join_date=now - timedelta(days=30),
        status=MemberStatus.ACTIVE,
        running_fee_balance=0,
    )
    session.add(m)
    session.flush()
    return m


@pytest.fixture
def item(session: Session) -> Item:
    it = Item(
        name="Cordless Drill [TEST-01]",
        category="Drills",
        replacement_value=50000,  # ₹500
        status=ItemStatus.AVAILABLE,
    )
    session.add(it)
    session.flush()
    return it


def test_rule_1_item_state_machine_valid_transitions(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 1: Available -> Reserved -> Checked Out -> Available."""
    assert item.status == ItemStatus.AVAILABLE

    # 1. Available -> Reserved
    loan = LoanService.reserve(session, member.id, item.id, now=now)
    assert item.status == ItemStatus.RESERVED
    assert loan.status == LoanStatus.RESERVED

    # 2. Reserved -> Checked Out
    checkout_time = now + timedelta(hours=2)
    loan = LoanService.checkout(session, loan.id, now=checkout_time)
    assert item.status == ItemStatus.CHECKED_OUT
    assert loan.status == LoanStatus.CHECKED_OUT

    # 3. Checked Out -> Available (on return)
    return_time = checkout_time + timedelta(days=3)
    loan, fee = LoanService.return_item(session, loan.id, now=return_time)
    assert item.status == ItemStatus.AVAILABLE
    assert loan.status == LoanStatus.RETURNED
    assert fee == 0


def test_rule_1_overdue_is_dynamically_computed_not_cron(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 1: From Checked Out, an item becomes Overdue automatically once due_at passes."""
    loan = LoanService.reserve(session, member.id, item.id, now=now - timedelta(days=10))
    loan = LoanService.checkout(session, loan.id, now=now - timedelta(days=9))
    # Due at checkout + 7 days = now - 2 days (currently 2 days overdue)
    assert loan.due_at == now - timedelta(days=2)

    # Overdue is derived dynamically at read time without a cron job
    assert LoanService.is_overdue(loan, now=now) is True
    overdue_loans = LoanService.get_overdue_loans(session, now=now)
    assert loan.id in [ol.id for ol in overdue_loans]


def test_rule_2_reservation_active_at_47h_59m(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 2: A reservation holds an item for 48 hours; valid at 47 hours 59 minutes."""
    reserved_time = now - timedelta(hours=47, minutes=59)
    loan = LoanService.reserve(session, member.id, item.id, now=reserved_time)

    # Checking out at 47h 59m elapsed must succeed
    checked_out = LoanService.checkout(session, loan.id, now=now)
    assert checked_out.status == LoanStatus.CHECKED_OUT
    assert item.status == ItemStatus.CHECKED_OUT


def test_rule_2_reservation_expires_at_exact_48_hours(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 2: A reservation expires at exactly 48 hours; item is effectively Available again."""
    reserved_time = now - timedelta(hours=48)
    loan = LoanService.reserve(session, member.id, item.id, now=reserved_time)

    # Checking out at exactly 48h must raise ReservationExpiredError and cancel reservation
    with pytest.raises(ReservationExpiredError):
        LoanService.checkout(session, loan.id, now=now)

    assert loan.status == LoanStatus.CANCELLED
    assert ItemService.get_effective_status(session, item.id, now=now) == ItemStatus.AVAILABLE

    # Another member can now reserve the effectively available item
    other_member = Member(
        name="Other Member",
        phone="+91-98765-00002",
        join_date=now,
        status=MemberStatus.ACTIVE,
    )
    session.add(other_member)
    session.flush()

    new_loan = LoanService.reserve(session, other_member.id, item.id, now=now)
    assert new_loan.status == LoanStatus.RESERVED
    assert new_loan.member_id == other_member.id


def test_rule_3_loan_period_is_7_days_from_checkout(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 3: Loan period is exactly 7 days from checkout."""
    loan = LoanService.reserve(session, member.id, item.id, now=now)
    loan = LoanService.checkout(session, loan.id, now=now + timedelta(hours=1))
    assert loan.due_at == loan.checked_out_at + timedelta(days=7)


def test_rule_3_late_fee_at_due_date_boundary():
    """Rule 3: 0 fee at or before due_at; ₹10 at 1 second past due_at."""
    now = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    due_at = now
    # 0 seconds overdue -> 0 fee
    assert calculate_late_fee(return_time=now, due_at=due_at, replacement_value=50000) == 0
    # 1 second overdue -> 1st day (1,000 paise = ₹10)
    assert (
        calculate_late_fee(
            return_time=now + timedelta(seconds=1), due_at=due_at, replacement_value=50000
        )
        == 1000
    )


def test_rule_3_late_fee_24h_increments():
    """Rule 3: 24h 0s late is ₹10; 24h 1s late is ₹20."""
    now = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    due_at = now
    assert (
        calculate_late_fee(
            return_time=now + timedelta(hours=24), due_at=due_at, replacement_value=50000
        )
        == 1000
    )
    assert (
        calculate_late_fee(
            return_time=now + timedelta(hours=24, seconds=1), due_at=due_at, replacement_value=50000
        )
        == 2000
    )


def test_rule_3_late_fee_capped_at_200_rupees():
    """Rule 3: Late fee capped at ₹200 (20,000 paise) per loan."""
    now = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    due_at = now
    # 25 days overdue on a ₹1,000 item -> capped at ₹200
    fee = calculate_late_fee(
        return_time=now + timedelta(days=25), due_at=due_at, replacement_value=100000
    )
    assert fee == 20000


def test_rule_3_late_fee_capped_at_replacement_value():
    """Rule 3: Late fee never exceeds the item's replacement value."""
    now = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    due_at = now
    # 25 days overdue on a ₹150 item (15,000 paise) -> capped at ₹150, not ₹200
    fee = calculate_late_fee(
        return_time=now + timedelta(days=25), due_at=due_at, replacement_value=15000
    )
    assert fee == 15000


def test_rule_4_member_at_most_3_active_loans(
    session: Session,
    member: Member,
    now: datetime,
):
    """Rule 4: A member may hold at most 3 active loans (Reserved, Checked Out, Overdue)."""
    items = [
        Item(
            name=f"Tool {i}", category="Tools", replacement_value=20000, status=ItemStatus.AVAILABLE
        )
        for i in range(1, 5)
    ]
    session.add_all(items)
    session.flush()

    # Reserve 3 tools (limit reached)
    for i in range(3):
        LoanService.reserve(session, member.id, items[i].id, now=now)

    # Attempting to reserve a 4th tool must be rejected
    with pytest.raises(ActiveLoanLimitExceededError):
        LoanService.reserve(session, member.id, items[3].id, now=now)


def test_rule_5_member_balance_boundary(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 5: Balance <= ₹100 is eligible; balance > ₹100 is blocked."""
    # Balance = ₹100 (10,000 paise) -> allowed
    member.running_fee_balance = 10000
    session.flush()
    loan = LoanService.reserve(session, member.id, item.id, now=now)
    assert loan.status == LoanStatus.RESERVED

    # Cancel loan to free item
    LoanService.cancel_reservation(session, loan.id, now=now)

    # Balance = ₹100.01 (10,001 paise) -> blocked
    member.running_fee_balance = 10001
    session.flush()
    with pytest.raises(MemberBalanceBlockError):
        LoanService.reserve(session, member.id, item.id, now=now)


def test_rule_5_overdue_14_days_boundary(
    session: Session,
    member: Member,
    now: datetime,
):
    """Rule 5: Any loan overdue > 14 days blocks borrowing; exactly 14 days is eligible."""
    item1 = Item(
        name="Tool 1", category="Tools", replacement_value=20000, status=ItemStatus.AVAILABLE
    )
    item2 = Item(
        name="Tool 2", category="Tools", replacement_value=20000, status=ItemStatus.AVAILABLE
    )
    session.add_all([item1, item2])
    session.flush()

    # Create checked-out loan exactly 14 days overdue
    loan1 = Loan(
        member_id=member.id,
        item_id=item1.id,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(days=21),
        checked_out_at=now - timedelta(days=21),
        due_at=now - timedelta(days=14),
    )
    item1.status = ItemStatus.CHECKED_OUT
    session.add(loan1)
    session.flush()

    # At exactly 14 days overdue, borrowing item2 is allowed
    loan2 = LoanService.reserve(session, member.id, item2.id, now=now)
    assert loan2.status == LoanStatus.RESERVED

    # Cancel loan2
    LoanService.cancel_reservation(session, loan2.id, now=now)

    # Move loan1 to 14 days + 1 second overdue -> blocked
    loan1.due_at = now - timedelta(days=14, seconds=1)
    session.flush()

    with pytest.raises(MemberOverdueBlockError):
        LoanService.reserve(session, member.id, item2.id, now=now)


def test_rule_6_return_of_item_not_checked_out_rejected(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 6: A return of an item that is not checked out is an error, not a no-op."""
    loan = LoanService.reserve(session, member.id, item.id, now=now)

    # Attempting to return a RESERVED loan must raise InvalidLoanStateError
    with pytest.raises(InvalidLoanStateError):
        LoanService.return_item(session, loan.id, now=now)

    # Check out loan
    LoanService.checkout(session, loan.id, now=now)

    # Return loan (succeeds)
    LoanService.return_item(session, loan.id, now=now + timedelta(days=2))

    # Double return: attempting to return already RETURNED loan must raise InvalidLoanStateError
    with pytest.raises(InvalidLoanStateError):
        LoanService.return_item(session, loan.id, now=now + timedelta(days=3))


def test_rule_7_suspended_member_cannot_transact(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Rule 7: Suspended members cannot reserve, check out, or transact."""
    MemberService.suspend_member(session, member.id)
    assert member.status == MemberStatus.SUSPENDED

    with pytest.raises(MemberSuspendedError):
        LoanService.reserve(session, member.id, item.id, now=now)

    # Reinstate member
    MemberService.reinstate_member(session, member.id)
    assert member.status == MemberStatus.ACTIVE
    loan = LoanService.reserve(session, member.id, item.id, now=now)
    assert loan.status == LoanStatus.RESERVED


def test_maintenance_cancels_pending_reservation(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Maintenance: Placing a RESERVED item into maintenance cancels the reservation."""
    loan = LoanService.reserve(session, member.id, item.id, now=now)
    assert item.status == ItemStatus.RESERVED

    # Place in maintenance
    m_item = ItemService.set_maintenance(session, item.id, now=now + timedelta(hours=1))
    assert m_item.status == ItemStatus.UNDER_MAINTENANCE
    assert loan.status == LoanStatus.CANCELLED
    assert loan.cancelled_at == now + timedelta(hours=1)


def test_maintenance_on_checked_out_item_permits_return(
    session: Session,
    member: Member,
    item: Item,
    now: datetime,
):
    """Maintenance: Marking a CHECKED_OUT item for maintenance leaves loan open and returnable."""
    loan = LoanService.reserve(session, member.id, item.id, now=now)
    LoanService.checkout(session, loan.id, now=now + timedelta(hours=1))
    assert item.status == ItemStatus.CHECKED_OUT

    # Staff marks item for maintenance while checked out
    ItemService.set_maintenance(session, item.id, now=now + timedelta(days=2))
    assert item.status == ItemStatus.UNDER_MAINTENANCE
    assert loan.status == LoanStatus.CHECKED_OUT

    # Member returns item -> succeeds!
    loan, fee = LoanService.return_item(session, loan.id, now=now + timedelta(days=5))
    assert loan.status == LoanStatus.RETURNED
    # Item remains under maintenance after return
    assert item.status == ItemStatus.UNDER_MAINTENANCE

    # Restoring item brings it back to AVAILABLE
    ItemService.restore_maintenance(session, item.id, now=now + timedelta(days=6))
    assert item.status == ItemStatus.AVAILABLE
