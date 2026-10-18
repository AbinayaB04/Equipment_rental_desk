"""Unit tests for LoanService application logic."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.exceptions import (
    ActiveLoanLimitExceededError,
    EntityNotFoundError,
    InvalidLoanStateError,
    ItemInMaintenanceError,
    ItemNotAvailableError,
    MemberBalanceBlockError,
    MemberSuspendedError,
    ReservationExpiredError,
)
from app.models.item import Item, ItemStatus
from app.models.loan import LoanStatus
from app.models.member import Member, MemberStatus
from app.services.loan_service import LoanService


def test_reserve_item_success(session: Session):
    """Reserving an available item creates a RESERVED loan and marks item RESERVED."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=now)

    assert loan.id is not None
    assert loan.status == LoanStatus.RESERVED
    assert loan.reserved_at == now
    assert loan.checked_out_at is None
    assert loan.due_at is None
    assert item.status == ItemStatus.RESERVED


def test_reserve_item_already_reserved_rejected(session: Session):
    """Reserving an item that already has an active reservation raises ItemNotAvailableError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member1 = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    member2 = Member(name="Bob", phone="+91-98765-43211", join_date=now)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member1, member2, item])
    session.flush()

    LoanService.reserve(session, member_id=member1.id, item_id=item.id, now=now)

    with pytest.raises(ItemNotAvailableError) as exc_info:
        LoanService.reserve(
            session, member_id=member2.id, item_id=item.id, now=now + timedelta(hours=1)
        )
    assert "already reserved" in str(exc_info.value)


def test_reserve_item_checked_out_rejected(session: Session):
    """Reserving an item that is currently checked out raises ItemNotAvailableError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member1 = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    member2 = Member(name="Bob", phone="+91-98765-43211", join_date=now)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member1, member2, item])
    session.flush()

    res = LoanService.reserve(session, member_id=member1.id, item_id=item.id, now=now)
    LoanService.checkout(session, loan_id=res.id, now=now + timedelta(hours=1))

    with pytest.raises(ItemNotAvailableError) as exc_info:
        LoanService.reserve(
            session, member_id=member2.id, item_id=item.id, now=now + timedelta(hours=2)
        )
    assert "currently checked out" in str(exc_info.value)


def test_reserve_item_under_maintenance_rejected(session: Session):
    """Reserving an item in maintenance raises ItemInMaintenanceError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(
        name="Broken Saw",
        category="Saws",
        replacement_value=30000,
        status=ItemStatus.UNDER_MAINTENANCE,
    )
    session.add_all([member, item])
    session.flush()

    with pytest.raises(ItemInMaintenanceError) as exc_info:
        LoanService.reserve(session, member_id=member.id, item_id=item.id, now=now)
    assert "under maintenance" in str(exc_info.value)


def test_reserve_expired_reservation_lazily_cancelled_and_succeeds(session: Session):
    """If previous reservation expired (>= 48h), a new member can reserve the item."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member1 = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    member2 = Member(name="Bob", phone="+91-98765-43211", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member1, member2, item])
    session.flush()

    old_loan = LoanService.reserve(session, member_id=member1.id, item_id=item.id, now=res_time)

    # 48 hours later, member2 reserves
    attempt_time = res_time + timedelta(hours=48)
    new_loan = LoanService.reserve(session, member_id=member2.id, item_id=item.id, now=attempt_time)

    assert old_loan.status == LoanStatus.CANCELLED
    assert old_loan.cancelled_at == attempt_time
    assert new_loan.id != old_loan.id
    assert new_loan.status == LoanStatus.RESERVED
    assert new_loan.member_id == member2.id
    assert item.status == ItemStatus.RESERVED


def test_reserve_nonexistent_entity_raises(session: Session):
    """Reserving with nonexistent member or item raises EntityNotFoundError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(EntityNotFoundError):
        LoanService.reserve(session, member_id=999, item_id=999, now=now)


def test_reserve_suspended_member_rejected(session: Session):
    """Suspended member cannot reserve an item."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(
        name="Bad Member", phone="+91-98765-43210", join_date=now, status=MemberStatus.SUSPENDED
    )
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    with pytest.raises(MemberSuspendedError):
        LoanService.reserve(session, member_id=member.id, item_id=item.id, now=now)


def test_reserve_member_exceeding_balance_limit_rejected(session: Session):
    """Member with running_fee_balance > ₹100 (10000 paise) cannot reserve."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(
        name="Debtor",
        phone="+91-98765-43210",
        join_date=now,
        running_fee_balance=10001,  # ₹100.01
    )
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    with pytest.raises(MemberBalanceBlockError):
        LoanService.reserve(session, member_id=member.id, item_id=item.id, now=now)


def test_reserve_member_with_three_active_loans_rejected(session: Session):
    """Member with 3 active loans cannot reserve a 4th item."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Maxed Borrower", phone="+91-98765-43210", join_date=now)
    items = [Item(name=f"Tool {i}", category="Tools", replacement_value=10000) for i in range(1, 5)]
    session.add(member)
    session.add_all(items)
    session.flush()

    for i in range(3):
        LoanService.reserve(session, member_id=member.id, item_id=items[i].id, now=now)

    with pytest.raises(ActiveLoanLimitExceededError):
        LoanService.reserve(session, member_id=member.id, item_id=items[3].id, now=now)


def test_checkout_success(session: Session):
    """Valid checkout sets loan CHECKED_OUT, due_at +7 days, item CHECKED_OUT."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)

    co_time = res_time + timedelta(hours=2)
    checked_out = LoanService.checkout(session, loan_id=loan.id, now=co_time)

    assert checked_out.status == LoanStatus.CHECKED_OUT
    assert checked_out.checked_out_at == co_time
    assert checked_out.due_at == co_time + timedelta(days=7)
    assert item.status == ItemStatus.CHECKED_OUT


def test_checkout_expired_reservation_cancels_and_raises(session: Session):
    """Attempting checkout on or after 48h boundary cancels loan and raises."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)

    exact_48h = res_time + timedelta(hours=48)
    with pytest.raises(ReservationExpiredError):
        LoanService.checkout(session, loan_id=loan.id, now=exact_48h)

    assert loan.status == LoanStatus.CANCELLED
    assert loan.cancelled_at == exact_48h
    assert item.status == ItemStatus.AVAILABLE


def test_checkout_invalid_loan_status_rejected(session: Session):
    """Checking out a loan that is already CHECKED_OUT or RETURNED raises InvalidLoanStateError."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)
    LoanService.checkout(session, loan_id=loan.id, now=res_time + timedelta(hours=1))

    with pytest.raises(InvalidLoanStateError) as exc_info:
        LoanService.checkout(session, loan_id=loan.id, now=res_time + timedelta(hours=2))
    assert "CHECKED_OUT" in str(exc_info.value)


def test_return_item_on_time_charges_zero_fee(session: Session):
    """Returning an item before or at due_at incurs ₹0 fee and sets item AVAILABLE."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)
    co_time = res_time + timedelta(hours=1)
    LoanService.checkout(session, loan_id=loan.id, now=co_time)

    ret_time = co_time + timedelta(days=6)  # 1 day early
    returned_loan, fee = LoanService.return_item(session, loan_id=loan.id, now=ret_time)

    assert returned_loan.status == LoanStatus.RETURNED
    assert returned_loan.returned_at == ret_time
    assert fee == 0
    assert returned_loan.fee_charged == 0
    assert member.running_fee_balance == 0
    assert item.status == ItemStatus.AVAILABLE


def test_return_item_overdue_assesses_fee_and_updates_member_balance(session: Session):
    """Returning overdue assesses ₹10/day fee and adds to member running balance."""
    res_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)
    co_time = res_time + timedelta(hours=1)
    LoanService.checkout(session, loan_id=loan.id, now=co_time)

    due_time = co_time + timedelta(days=7)
    ret_time = due_time + timedelta(days=3)  # 3 days late -> 3000 paise
    returned_loan, fee = LoanService.return_item(session, loan_id=loan.id, now=ret_time)

    assert returned_loan.status == LoanStatus.RETURNED
    assert fee == 3000
    assert returned_loan.fee_charged == 3000
    assert member.running_fee_balance == 3000
    assert item.status == ItemStatus.AVAILABLE


def test_double_return_rejected_and_does_not_double_charge(session: Session):
    """Returning an already RETURNED loan raises InvalidLoanStateError without modifying balance."""
    res_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)
    co_time = res_time + timedelta(hours=1)
    LoanService.checkout(session, loan_id=loan.id, now=co_time)

    due_time = co_time + timedelta(days=7)
    ret_time = due_time + timedelta(days=2)  # 2 days late = 2000 paise
    LoanService.return_item(session, loan_id=loan.id, now=ret_time)
    assert member.running_fee_balance == 2000

    # Second return attempt
    with pytest.raises(InvalidLoanStateError) as exc_info:
        LoanService.return_item(session, loan_id=loan.id, now=ret_time + timedelta(hours=1))
    assert "RETURNED" in str(exc_info.value)
    # Verify balance was NOT double-charged
    assert member.running_fee_balance == 2000


def test_return_reserved_loan_rejected(session: Session):
    """Returning a loan that is in RESERVED state raises InvalidLoanStateError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=now)

    with pytest.raises(InvalidLoanStateError) as exc_info:
        LoanService.return_item(session, loan_id=loan.id, now=now)
    assert "RESERVED" in str(exc_info.value)


def test_cancel_reservation_success(session: Session):
    """Cancelling a reservation sets loan CANCELLED and returns item to AVAILABLE."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=now)
    cancelled_loan = LoanService.cancel_reservation(
        session, loan_id=loan.id, now=now + timedelta(hours=1)
    )

    assert cancelled_loan.status == LoanStatus.CANCELLED
    assert cancelled_loan.cancelled_at == now + timedelta(hours=1)
    assert item.status == ItemStatus.AVAILABLE


def test_cancel_checked_out_loan_rejected(session: Session):
    """Cancelling a loan that is CHECKED_OUT raises InvalidLoanStateError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=now)
    LoanService.checkout(session, loan_id=loan.id, now=now + timedelta(hours=1))

    with pytest.raises(InvalidLoanStateError):
        LoanService.cancel_reservation(session, loan_id=loan.id, now=now + timedelta(hours=2))


def test_is_overdue_and_get_overdue_loans(session: Session):
    """Overdue status is dynamically computed based on due_at."""
    co_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    due_time = co_time + timedelta(days=7)  # Oct 8 10:00 UTC
    member = Member(name="Alice", phone="+91-98765-43210", join_date=co_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=co_time)
    LoanService.checkout(session, loan_id=loan.id, now=co_time)

    # 1 second before due -> not overdue
    assert not LoanService.is_overdue(loan, now=due_time - timedelta(seconds=1))
    assert not LoanService.get_overdue_loans(session, now=due_time - timedelta(seconds=1))

    # Exactly due -> not overdue
    assert not LoanService.is_overdue(loan, now=due_time)

    # 1 second after due -> overdue
    assert LoanService.is_overdue(loan, now=due_time + timedelta(seconds=1))
    overdue_list = LoanService.get_overdue_loans(session, now=due_time + timedelta(seconds=1))
    assert len(overdue_list) == 1
    assert overdue_list[0].id == loan.id


def test_checkout_time_preceding_reservation_time_rejected(session: Session):
    """Checkout with a timestamp earlier than reserved_at raises InvalidLoanStateError."""
    res_time = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)

    with pytest.raises(InvalidLoanStateError) as exc_info:
        LoanService.checkout(session, loan_id=loan.id, now=res_time - timedelta(minutes=5))
    assert "earlier than reservation time" in str(exc_info.value)


def test_return_time_preceding_checkout_time_rejected(session: Session):
    """Return with a timestamp earlier than checked_out_at raises InvalidLoanStateError."""
    res_time = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)
    co_time = res_time + timedelta(hours=1)
    LoanService.checkout(session, loan_id=loan.id, now=co_time)

    with pytest.raises(InvalidLoanStateError) as exc_info:
        LoanService.return_item(session, loan_id=loan.id, now=co_time - timedelta(minutes=10))
    assert "earlier than check-out time" in str(exc_info.value)


def test_cancel_time_preceding_reservation_time_rejected(session: Session):
    """Attempting cancellation earlier than reserved_at raises InvalidLoanStateError."""
    res_time = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)

    with pytest.raises(InvalidLoanStateError) as exc_info:
        LoanService.cancel_reservation(
            session, loan_id=loan.id, now=res_time - timedelta(minutes=5)
        )
    assert "earlier than reservation time" in str(exc_info.value)


def test_settle_expired_reservation_unit(session: Session):
    """settle_expired_reservation cancels expired reservations and ignores unexpired ones."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)

    # At 47h -> not expired, settle returns was_expired=False
    _, was_expired = LoanService.settle_expired_reservation(
        session, loan_id=loan.id, now=res_time + timedelta(hours=47)
    )
    assert was_expired is False
    assert loan.status == LoanStatus.RESERVED
    assert item.status == ItemStatus.RESERVED

    # At 48h -> expired, settle cancels loan and restores item to AVAILABLE
    settled_loan, was_expired = LoanService.settle_expired_reservation(
        session, loan_id=loan.id, now=res_time + timedelta(hours=48)
    )
    assert was_expired is True
    assert settled_loan.status == LoanStatus.CANCELLED
    assert item.status == ItemStatus.AVAILABLE


def test_checkout_with_outcome_success_and_expiry(session: Session):
    """checkout_with_outcome returns CheckoutOutcome without raising on expiry."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    item = Item(name="Cordless Drill", category="Drills", replacement_value=50000)
    session.add_all([member, item])
    session.flush()

    loan = LoanService.reserve(session, member_id=member.id, item_id=item.id, now=res_time)

    # Valid checkout at 2h -> success
    outcome_valid = LoanService.checkout_with_outcome(
        session, loan_id=loan.id, now=res_time + timedelta(hours=2)
    )
    assert outcome_valid.success is True
    assert outcome_valid.is_expired is False
    assert outcome_valid.loan.status == LoanStatus.CHECKED_OUT

    # Now create another reservation and test expiry outcome
    item2 = Item(name="Saw", category="Saws", replacement_value=40000)
    session.add(item2)
    session.flush()
    loan2 = LoanService.reserve(session, member_id=member.id, item_id=item2.id, now=res_time)

    outcome_expired = LoanService.checkout_with_outcome(
        session, loan_id=loan2.id, now=res_time + timedelta(hours=48)
    )
    assert outcome_expired.success is False
    assert outcome_expired.is_expired is True
    assert "expired" in outcome_expired.rejection_reason.lower()
    assert loan2.status == LoanStatus.CANCELLED
    assert item2.status == ItemStatus.AVAILABLE


def test_list_loans_service(session: Session):
    """LoanService.list_loans supports member_id, item_id, status filtering and pagination."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    m1 = Member(name="Member 1", phone="+91-1", join_date=now)
    m2 = Member(name="Member 2", phone="+91-2", join_date=now)
    i1 = Item(name="Item 1", category="Cat", replacement_value=10000)
    i2 = Item(name="Item 2", category="Cat", replacement_value=10000)
    session.add_all([m1, m2, i1, i2])
    session.flush()

    l1 = LoanService.reserve(session, member_id=m1.id, item_id=i1.id, now=now)
    l2 = LoanService.reserve(session, member_id=m2.id, item_id=i2.id, now=now)
    LoanService.checkout(session, loan_id=l2.id, now=now + timedelta(hours=1))

    all_loans = LoanService.list_loans(session)
    assert len(all_loans) >= 2

    # Filter by member
    m1_loans = LoanService.list_loans(session, member_id=m1.id)
    assert len(m1_loans) == 1
    assert m1_loans[0].id == l1.id

    # Filter by item
    i2_loans = LoanService.list_loans(session, item_id=i2.id)
    assert len(i2_loans) == 1
    assert i2_loans[0].id == l2.id

    # Filter by status
    reserved_loans = LoanService.list_loans(session, status=LoanStatus.RESERVED)
    assert any(loan.id == l1.id for loan in reserved_loans)
    assert not any(loan.id == l2.id for loan in reserved_loans)
