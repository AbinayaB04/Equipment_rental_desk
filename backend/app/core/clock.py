from datetime import UTC, datetime

from fastapi import HTTPException, Request, status

from app.core.config import Settings


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


def parse_test_clock_header(header_value: str) -> datetime:
    """Parse an ISO-8601 timestamp string from the X-Test-Clock header.

    Requires a timezone-aware timestamp (ending in 'Z' or with explicit offset like '+05:30').
    Rejects naive timestamps or invalid format with ValueError.
    Normalizes to UTC.
    """
    if not header_value or not isinstance(header_value, str):
        raise ValueError("X-Test-Clock header value must not be empty.")

    try:
        dt = datetime.fromisoformat(header_value.strip())
    except Exception as e:
        raise ValueError(
            f"Invalid X-Test-Clock format: {e}. "
            "Expected ISO-8601 string (e.g. '2026-10-25T14:00:00Z')."
        ) from e

    if dt.tzinfo is None:
        raise ValueError(
            "X-Test-Clock timestamp must be timezone-aware (e.g. '2026-10-25T14:00:00Z')."
        )

    return dt.astimezone(UTC)


def get_request_clock(request: Request) -> datetime:
    """FastAPI dependency to retrieve the request clock time.

    If X-Test-Clock is present:
    - Verifies reviewer test clock is enabled for the environment (always disabled in production).
    - Verifies X-Test-Clock-Key if TEST_CLOCK_KEY is configured.
    - Parses and normalizes the timezone-aware timestamp to UTC.
    - Rejects invalid, naive, disabled, or unauthorized clock overrides with safe client errors.

    If X-Test-Clock is absent:
    - Returns get_now() (real UTC time).
    """
    header_val = request.headers.get("X-Test-Clock")
    if not header_val:
        return get_now()

    settings: Settings = getattr(request.app.state, "settings", None) or Settings.from_env()

    # 1. Enforce production / environment disabling
    if not settings.allow_test_clock:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer test clock is disabled in this environment.",
        )

    # 2. Enforce authorization key if configured
    if settings.test_clock_key:
        key_val = request.headers.get("X-Test-Clock-Key")
        if not key_val or key_val != settings.test_clock_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing test clock authorization key.",
            )

    # 3. Parse timezone-aware timestamp and normalize to UTC
    try:
        return parse_test_clock_header(header_val)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
