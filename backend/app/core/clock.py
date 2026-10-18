"""Time and clock utilities ensuring consistent UTC handling across all databases."""

from datetime import UTC, datetime


def get_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime object is timezone-aware in UTC.

    Handles SQLite and other drivers where TIMESTAMP columns are retrieved without tzinfo.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
