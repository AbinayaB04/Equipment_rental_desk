"""Item application service handling inventory status and maintenance transitions."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import ensure_utc
from app.domain.exceptions import (
    EntityNotFoundError,
    InvalidItemStateError,
)
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus

RESERVATION_DURATION = timedelta(hours=48)


class ItemService:
    """Service handling item inventory, maintenance, and availability queries."""

    @staticmethod
    def get_item(session: Session, item_id: int) -> Item:
        """Retrieve an item by ID or raise EntityNotFoundError."""
        item = session.get(Item, item_id)
        if item is None:
            raise EntityNotFoundError(f"Item with ID {item_id} not found.")
        return item

    @classmethod
    def get_effective_status(
        cls,
        session: Session,
        item_id: int,
        now: datetime | None = None,
    ) -> ItemStatus:
        """Derive the effective status of an item considering dynamic reservation expiry."""
        item = cls.get_item(session, item_id)
        current_time = now or datetime.now(UTC)

        if item.status == ItemStatus.UNDER_MAINTENANCE:
            return ItemStatus.UNDER_MAINTENANCE

        if item.status == ItemStatus.CHECKED_OUT:
            return ItemStatus.CHECKED_OUT

        if item.status == ItemStatus.RESERVED:
            # Check latest reservation
            latest_loan = (
                session.query(Loan)
                .filter(Loan.item_id == item_id, Loan.status == LoanStatus.RESERVED)
                .order_by(Loan.reserved_at.desc())
                .first()
            )
            if latest_loan:
                latest_res_at = ensure_utc(latest_loan.reserved_at)
                if latest_res_at and current_time >= latest_res_at + RESERVATION_DURATION:
                    # Dynamically expired: effectively available for new reservations
                    return ItemStatus.AVAILABLE
            return ItemStatus.RESERVED

        return ItemStatus.AVAILABLE

    @classmethod
    def set_maintenance(
        cls,
        session: Session,
        item_id: int,
        now: datetime | None = None,
    ) -> Item:
        """Place an item into maintenance.

        Rules:
        - If item was RESERVED: cancels the active reservation (setting Loan.status=CANCELLED,
          cancelled_at=now) and sets item to UNDER_MAINTENANCE.
        - If item was CHECKED_OUT: leaves the loan active and returnable, but marks the item
          UNDER_MAINTENANCE so that upon return it remains under maintenance.
        - If item was AVAILABLE: sets status to UNDER_MAINTENANCE.
        """
        current_time = now or datetime.now(UTC)
        item = session.query(Item).filter(Item.id == item_id).with_for_update().one_or_none()
        if item is None:
            raise EntityNotFoundError(f"Item with ID {item_id} not found.")

        # If there is an active reservation, cancel it
        active_reservation = (
            session.query(Loan)
            .filter(Loan.item_id == item_id, Loan.status == LoanStatus.RESERVED)
            .with_for_update()
            .first()
        )
        if active_reservation:
            active_reservation.status = LoanStatus.CANCELLED
            active_reservation.cancelled_at = current_time

        item.status = ItemStatus.UNDER_MAINTENANCE
        session.flush()
        return item

    @classmethod
    def restore_maintenance(
        cls,
        session: Session,
        item_id: int,
        now: datetime | None = None,
    ) -> Item:
        """Restore an item from maintenance.

        Rules:
        - Item must currently be UNDER_MAINTENANCE.
        - If there is an outstanding CHECKED_OUT loan, status returns to CHECKED_OUT.
        - Otherwise, status returns to AVAILABLE.
        """
        item = session.query(Item).filter(Item.id == item_id).with_for_update().one_or_none()
        if item is None:
            raise EntityNotFoundError(f"Item with ID {item_id} not found.")

        if item.status != ItemStatus.UNDER_MAINTENANCE:
            raise InvalidItemStateError(
                f"Cannot restore item {item_id} because its status is {item.status.value}, "
                "not UNDER_MAINTENANCE."
            )

        current_time = ensure_utc(now) or datetime.now(UTC)

        # Assumption 14: Settle any lingering reservation on this item in the same transaction
        lingering_reservation = (
            session.query(Loan)
            .filter(Loan.item_id == item_id, Loan.status == LoanStatus.RESERVED)
            .with_for_update()
            .first()
        )
        if lingering_reservation:
            lingering_reservation.status = LoanStatus.CANCELLED
            lingering_reservation.cancelled_at = current_time

        active_checkout = (
            session.query(Loan)
            .filter(Loan.item_id == item_id, Loan.status == LoanStatus.CHECKED_OUT)
            .first()
        )
        if active_checkout:
            item.status = ItemStatus.CHECKED_OUT
        else:
            item.status = ItemStatus.AVAILABLE

        session.flush()
        return item

    @classmethod
    def list_items(
        cls,
        session: Session,
        category: str | None = None,
        status: ItemStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Item]:
        """List items with optional category/status filters and pagination."""
        query = session.query(Item)
        if category is not None:
            query = query.filter(Item.category == category)
        if status is not None:
            query = query.filter(Item.status == status)
        return query.order_by(Item.id.asc()).offset(offset).limit(limit).all()

    @classmethod
    def create_item(
        cls,
        session: Session,
        name: str,
        category: str,
        replacement_value: int,
        condition_note: str | None = None,
    ) -> Item:
        """Create a new item in AVAILABLE status."""
        cleaned_name = name.strip()
        cleaned_category = category.strip()
        if not cleaned_name:
            raise ValueError("Item name must not be empty.")
        if not cleaned_category:
            raise ValueError("Item category must not be empty.")
        if replacement_value <= 0:
            raise ValueError("Replacement value must be greater than 0 paise.")

        item = Item(
            name=cleaned_name,
            category=cleaned_category,
            replacement_value=replacement_value,
            condition_note=condition_note.strip() if condition_note else None,
            status=ItemStatus.AVAILABLE,
        )
        session.add(item)
        session.flush()
        return item

    @classmethod
    def update_item(
        cls,
        session: Session,
        item_id: int,
        name: str | None = None,
        category: str | None = None,
        replacement_value: int | None = None,
        condition_note: str | None = None,
    ) -> Item:
        """Update permitted metadata (name, category, replacement_value, condition_note).

        Note: Status cannot be updated via this method; maintenance transitions
        must use set_maintenance() and restore_maintenance().
        """
        item = cls.get_item(session, item_id)
        if name is not None:
            cleaned_name = name.strip()
            if not cleaned_name:
                raise ValueError("Item name must not be empty.")
            item.name = cleaned_name
        if category is not None:
            cleaned_category = category.strip()
            if not cleaned_category:
                raise ValueError("Item category must not be empty.")
            item.category = cleaned_category
        if replacement_value is not None:
            if replacement_value <= 0:
                raise ValueError("Replacement value must be greater than 0 paise.")
            item.replacement_value = replacement_value
        if condition_note is not None:
            item.condition_note = condition_note.strip() if condition_note else None
        session.flush()
        return item
