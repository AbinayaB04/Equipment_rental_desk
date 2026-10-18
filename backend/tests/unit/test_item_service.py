"""Unit tests for ItemService application logic."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.exceptions import EntityNotFoundError, InvalidItemStateError
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member
from app.services.item_service import ItemService


def test_get_item_not_found(session: Session):
    """Querying a nonexistent item raises EntityNotFoundError."""
    with pytest.raises(EntityNotFoundError):
        ItemService.get_item(session, 999)


def test_set_maintenance_on_available_item(session: Session):
    """Setting maintenance on AVAILABLE item transitions it to UNDER_MAINTENANCE."""
    item = Item(name="Table Saw", category="Saws", replacement_value=60000)
    session.add(item)
    session.flush()

    assert item.status == ItemStatus.AVAILABLE
    updated = ItemService.set_maintenance(session, item.id)
    assert updated.status == ItemStatus.UNDER_MAINTENANCE


def test_set_maintenance_on_reserved_item_cancels_reservation(session: Session):
    """Setting maintenance on a RESERVED item cancels the reservation and sets UNDER_MAINTENANCE."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(
        name="Table Saw",
        category="Saws",
        replacement_value=60000,
        status=ItemStatus.RESERVED,
    )
    session.add_all([member, item])
    session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now,
    )
    session.add(loan)
    session.flush()

    ItemService.set_maintenance(session, item.id, now=now + timedelta(hours=1))

    assert item.status == ItemStatus.UNDER_MAINTENANCE
    assert loan.status == LoanStatus.CANCELLED
    assert loan.cancelled_at == now + timedelta(hours=1)


def test_set_maintenance_on_checked_out_item_leaves_loan_active(session: Session):
    """Setting maintenance on CHECKED_OUT item keeps loan active and sets item UNDER_MAINTENANCE."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(
        name="Table Saw",
        category="Saws",
        replacement_value=60000,
        status=ItemStatus.CHECKED_OUT,
    )
    session.add_all([member, item])
    session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(hours=2),
        checked_out_at=now,
        due_at=now + timedelta(days=7),
    )
    session.add(loan)
    session.flush()

    ItemService.set_maintenance(session, item.id, now=now + timedelta(hours=1))

    assert item.status == ItemStatus.UNDER_MAINTENANCE
    # Loan remains CHECKED_OUT and returnable
    assert loan.status == LoanStatus.CHECKED_OUT


def test_restore_maintenance_to_available_and_checked_out(session: Session):
    """Restoring maintenance returns item to AVAILABLE, or CHECKED_OUT if currently on loan."""
    item1 = Item(
        name="Table Saw",
        category="Saws",
        replacement_value=60000,
        status=ItemStatus.UNDER_MAINTENANCE,
    )
    session.add(item1)
    session.flush()

    # Case 1: no active checkout -> AVAILABLE
    restored1 = ItemService.restore_maintenance(session, item1.id)
    assert restored1.status == ItemStatus.AVAILABLE

    # Case 2: active checkout -> returns to CHECKED_OUT
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item2 = Item(
        name="Router",
        category="Routers",
        replacement_value=40000,
        status=ItemStatus.UNDER_MAINTENANCE,
    )
    session.add_all([member, item2])
    session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item2.id,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(hours=2),
        checked_out_at=now,
        due_at=now + timedelta(days=7),
    )
    session.add(loan)
    session.flush()

    restored2 = ItemService.restore_maintenance(session, item2.id)
    assert restored2.status == ItemStatus.CHECKED_OUT


def test_restore_maintenance_invalid_state_raises(session: Session):
    """Restoring an item that is not UNDER_MAINTENANCE raises InvalidItemStateError."""
    item = Item(name="Table Saw", category="Saws", replacement_value=60000)
    session.add(item)
    session.flush()

    with pytest.raises(InvalidItemStateError):
        ItemService.restore_maintenance(session, item.id)


def test_get_effective_status(session: Session):
    """Dynamic effective status reflects reservation expiry without a cron job."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(
        name="Table Saw", category="Saws", replacement_value=60000, status=ItemStatus.RESERVED
    )
    session.add_all([member, item])
    session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now,
    )
    session.add(loan)
    session.flush()

    # 47 hours later -> still RESERVED
    status_47h = ItemService.get_effective_status(session, item.id, now=now + timedelta(hours=47))
    assert status_47h == ItemStatus.RESERVED

    # 48 hours later -> dynamically AVAILABLE
    status_48h = ItemService.get_effective_status(session, item.id, now=now + timedelta(hours=48))
    assert status_48h == ItemStatus.AVAILABLE


def test_restore_maintenance_settles_lingering_reservation(session: Session):
    """Restoring an item cancels any lingering reservation per Assumption 14."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=now)
    item = Item(
        name="Table Saw",
        category="Saws",
        replacement_value=60000,
        status=ItemStatus.UNDER_MAINTENANCE,
    )
    session.add_all([member, item])
    session.flush()

    lingering_loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now - timedelta(hours=50),
    )
    session.add(lingering_loan)
    session.flush()

    restored = ItemService.restore_maintenance(session, item.id, now=now)
    assert restored.status == ItemStatus.AVAILABLE
    assert lingering_loan.status == LoanStatus.CANCELLED
    assert lingering_loan.cancelled_at == now
