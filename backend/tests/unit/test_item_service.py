"""Unit tests for ItemService application logic."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.exceptions import (
    EntityHasAssociatedRecordsError,
    EntityNotFoundError,
    InvalidItemStateError,
)
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


def test_create_item_service(session: Session):
    """ItemService.create_item initializes item in AVAILABLE status."""
    item = ItemService.create_item(
        session,
        name=" Jigsaw 500W ",
        category=" Saws ",
        replacement_value=35000,
        condition_note="Brand new in box",
    )
    assert item.id is not None
    assert item.name == "Jigsaw 500W"
    assert item.category == "Saws"
    assert item.replacement_value == 35000
    assert item.condition_note == "Brand new in box"
    assert item.status == ItemStatus.AVAILABLE

    # Validation errors
    with pytest.raises(ValueError, match="name"):
        ItemService.create_item(session, name="  ", category="Saws", replacement_value=1000)
    with pytest.raises(ValueError, match="category"):
        ItemService.create_item(session, name="Tool", category="  ", replacement_value=1000)
    with pytest.raises(ValueError, match="paise"):
        ItemService.create_item(session, name="Tool", category="Saws", replacement_value=0)


def test_update_item_service(session: Session):
    """ItemService.update_item updates metadata without altering status."""
    item = ItemService.create_item(
        session, name="Drill A", category="Drills", replacement_value=20000
    )
    assert item.status == ItemStatus.AVAILABLE

    updated = ItemService.update_item(
        session,
        item.id,
        name="Drill A Pro",
        category="Heavy Drills",
        replacement_value=25000,
        condition_note="Upgraded chuck",
    )
    assert updated.name == "Drill A Pro"
    assert updated.category == "Heavy Drills"
    assert updated.replacement_value == 25000
    assert updated.condition_note == "Upgraded chuck"
    assert updated.status == ItemStatus.AVAILABLE

    # Negative replacement value raises ValueError
    with pytest.raises(ValueError, match="paise"):
        ItemService.update_item(session, item.id, replacement_value=-10)

    # Nonexistent item raises EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        ItemService.update_item(session, 99999, name="Ghost")


def test_list_items_service(session: Session):
    """ItemService.list_items supports category/status filtering and pagination."""
    i1 = ItemService.create_item(
        session, name="Circular Saw", category="Saws", replacement_value=50000
    )
    i2 = ItemService.create_item(
        session, name="Hammer Drill", category="Drills", replacement_value=40000
    )
    ItemService.set_maintenance(session, i2.id)

    all_items = ItemService.list_items(session)
    assert len(all_items) >= 2

    saws_only = ItemService.list_items(session, category="Saws")
    assert any(item.id == i1.id for item in saws_only)
    assert all(item.category == "Saws" for item in saws_only)

    avail_only = ItemService.list_items(session, status=ItemStatus.AVAILABLE)
    assert any(item.id == i1.id for item in avail_only)
    assert all(item.status == ItemStatus.AVAILABLE for item in avail_only)

    maint_only = ItemService.list_items(session, status=ItemStatus.UNDER_MAINTENANCE)
    assert any(item.id == i2.id for item in maint_only)
    assert all(item.status == ItemStatus.UNDER_MAINTENANCE for item in maint_only)


def test_list_items_service_search(session: Session):
    """ItemService.list_items supports case-insensitive partial search on name and category."""
    i1 = ItemService.create_item(
        session, name="Makita Router 1/2-inch", category="Woodworking", replacement_value=45000
    )
    i2 = ItemService.create_item(
        session, name="Angle Grinder 4-1/2-inch", category="Metalworking", replacement_value=30000
    )

    # Search by name substring
    name_res = ItemService.list_items(session, q="router")
    assert any(item.id == i1.id for item in name_res)
    assert not any(item.id == i2.id for item in name_res)

    # Search by category substring
    cat_res = ItemService.list_items(session, q="metal")
    assert any(item.id == i2.id for item in cat_res)
    assert not any(item.id == i1.id for item in cat_res)

    # Whitespace-only search returns all items
    ws_res = ItemService.list_items(session, q="   ")
    assert len(ws_res) >= 2


def test_delete_item_service_success(session: Session):
    """ItemService.delete_item deletes an available unborrowed item successfully."""
    item = Item(name="Old Ladder", category="Ladders", replacement_value=12000)
    session.add(item)
    session.flush()

    ItemService.delete_item(session, item.id)
    session.flush()

    with pytest.raises(EntityNotFoundError):
        ItemService.get_item(session, item.id)


def test_delete_item_service_in_maintenance_success(session: Session):
    """ItemService.delete_item deletes an unborrowed maintenance item successfully."""
    item = Item(
        name="Broken Level",
        category="Levels",
        replacement_value=4000,
        status=ItemStatus.UNDER_MAINTENANCE,
    )
    session.add(item)
    session.flush()

    ItemService.delete_item(session, item.id)
    session.flush()

    with pytest.raises(EntityNotFoundError):
        ItemService.get_item(session, item.id)


def test_delete_item_service_nonexistent(session: Session):
    """ItemService.delete_item raises EntityNotFoundError for missing item."""
    with pytest.raises(EntityNotFoundError):
        ItemService.delete_item(session, 999999)


def test_delete_item_service_with_loan_rejected(session: Session):
    """ItemService.delete_item raises EntityHasAssociatedRecordsError when item has loan records."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Borrower", phone="+91-99999-22222", join_date=now)
    item = Item(name="Loaned Item", category="Tools", replacement_value=8000)
    session.add_all([member, item])
    session.flush()

    loan = Loan(member_id=member.id, item_id=item.id, reserved_at=now, status=LoanStatus.RESERVED)
    session.add(loan)
    session.flush()

    with pytest.raises(EntityHasAssociatedRecordsError):
        ItemService.delete_item(session, item.id)


def test_delete_item_service_checked_out_state_rejected(session: Session):
    """ItemService.delete_item raises EntityHasAssociatedRecordsError if CHECKED_OUT."""
    item = Item(
        name="Active Tool",
        category="Tools",
        replacement_value=8000,
        status=ItemStatus.CHECKED_OUT,
    )
    session.add(item)
    session.flush()

    with pytest.raises(EntityHasAssociatedRecordsError):
        ItemService.delete_item(session, item.id)
