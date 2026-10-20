"""Item API routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.clock import get_request_clock
from app.core.database import get_db
from app.models.item import ItemStatus
from app.schemas.common import PaginationLimit, PaginationOffset, PositiveId
from app.schemas.item import ItemCreate, ItemResponse, ItemUpdate
from app.services.item_service import ItemService

router = APIRouter()


@router.get("", response_model=list[ItemResponse])
def list_items(
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[str | None, Query(description="Filter by item category")] = None,
    status_filter: Annotated[
        ItemStatus | None,
        Query(alias="status", description="Filter by item status"),
    ] = None,
    limit: PaginationLimit = 100,
    offset: PaginationOffset = 0,
) -> list[ItemResponse]:
    """List items with optional category/status filters and pagination."""
    return ItemService.list_items(
        db,
        category=category,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ItemResponse:
    """Create a new equipment item in AVAILABLE status."""
    return ItemService.create_item(
        db,
        name=payload.name,
        category=payload.category,
        replacement_value=payload.replacement_value,
        condition_note=payload.condition_note,
    )


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
) -> ItemResponse:
    """Retrieve a single equipment item by ID."""
    return ItemService.get_item(db, item_id=item_id)


@router.patch("/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: PositiveId,
    payload: ItemUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ItemResponse:
    """Update permitted metadata (name, category, replacement_value, condition_note)."""
    return ItemService.update_item(
        db,
        item_id=item_id,
        name=payload.name,
        category=payload.category,
        replacement_value=payload.replacement_value,
        condition_note=payload.condition_note,
    )


@router.post("/{item_id}/maintenance", response_model=ItemResponse)
def set_maintenance(
    item_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> ItemResponse:
    """Place an item into maintenance, cancelling active reservation if any."""
    return ItemService.set_maintenance(db, item_id=item_id, now=now)


@router.post("/{item_id}/restore-maintenance", response_model=ItemResponse)
def restore_maintenance(
    item_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> ItemResponse:
    """Restore an item from maintenance back to AVAILABLE or CHECKED_OUT."""
    return ItemService.restore_maintenance(db, item_id=item_id, now=now)


@router.post("/{item_id}/restore", response_model=ItemResponse, include_in_schema=False)
def restore_maintenance_alias(
    item_id: PositiveId,
    db: Annotated[Session, Depends(get_db)],
    now: Annotated[datetime, Depends(get_request_clock)],
) -> ItemResponse:
    """Alias for restore_maintenance."""
    return ItemService.restore_maintenance(db, item_id=item_id, now=now)
