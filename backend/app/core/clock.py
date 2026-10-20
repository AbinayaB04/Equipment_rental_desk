import hmac
from datetime import UTC, datetime, timedelta

from fastapi import Request, status

from app.core.config import Settings

# Bounded to +/- 90 days from server time to prevent date-math overflow and ensure
# realistic review windows.
TEST_CLOCK_MAX_OFFSET = timedelta(days=90)


class TestClockError(Exception):
    """Exception raised when an incoming X-Test-Clock header fails validation or authorization."""

    def __init__(self, status_code: int, error: str, detail: str, code: str):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        self.code = code
        super().__init__(detail)


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

    if header_value != header_value.strip():
        raise ValueError("X-Test-Clock header must not contain leading or trailing whitespace.")

    if len(header_value) > 64:
        raise ValueError("X-Test-Clock header exceeds maximum supported length (64 characters).")

    try:
        dt = datetime.fromisoformat(header_value)
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


def validate_and_resolve_test_clock(request: Request, settings: Settings) -> datetime | None:
    """Validate incoming X-Test-Clock and X-Test-Clock-Key headers in request scope.

    Validates that:
    1. Test clock is enabled in settings (otherwise HTTP 403 TEST_CLOCK_DISABLED).
    2. Authorization key matches if configured (otherwise HTTP 403 TEST_CLOCK_UNAUTHORIZED).
    3. Timestamp is valid ISO-8601, timezone-aware, bounded in length, and within 90 days of
       system time (otherwise HTTP 422 INVALID_TEST_CLOCK).

    Returns the normalized UTC datetime if a valid clock was provided, or None if absent.
    """
    header_val = request.headers.get("X-Test-Clock")
    if header_val is None:
        return None

    # 1. Enforce environment disabling
    if not settings.allow_test_clock:
        raise TestClockError(
            status_code=status.HTTP_403_FORBIDDEN,
            error="Forbidden",
            detail="Reviewer test clock is disabled in this environment.",
            code="TEST_CLOCK_DISABLED",
        )

    # 2. Enforce authorization key if configured (using constant-time comparison)
    if settings.test_clock_key:
        key_val = request.headers.get("X-Test-Clock-Key", "")
        if not key_val or not hmac.compare_digest(key_val, settings.test_clock_key):
            raise TestClockError(
                status_code=status.HTTP_403_FORBIDDEN,
                error="Forbidden",
                detail="Invalid or missing test clock authorization key.",
                code="TEST_CLOCK_UNAUTHORIZED",
            )

    # 3. Parse and validate timestamp format and bounds
    try:
        dt_utc = parse_test_clock_header(header_val)
    except ValueError as e:
        raise TestClockError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error="Unprocessable Entity",
            detail=str(e),
            code="INVALID_TEST_CLOCK",
        ) from e

    # 4. Enforce 90-day window check against real server now
    # (with 500ms leeway for client-server execution delta)
    real_now = get_now()
    if abs(dt_utc - real_now) > (TEST_CLOCK_MAX_OFFSET + timedelta(milliseconds=500)):
        raise TestClockError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error="Unprocessable Entity",
            detail="X-Test-Clock must be within 90 days of the server time.",
            code="INVALID_TEST_CLOCK",
        )

    return dt_utc


def get_request_clock(request: Request) -> datetime:
    """FastAPI dependency to retrieve the request clock time.

    If X-Test-Clock was processed and active in request scope, returns that datetime.
    Otherwise returns real UTC system time.
    """
    if getattr(request.state, "is_test_clock", False) and getattr(
        request.state, "test_clock", None
    ):
        return request.state.test_clock

    # Fallback if accessed without middleware
    header_val = request.headers.get("X-Test-Clock")
    if header_val is not None:
        settings: Settings = getattr(request.app.state, "settings", None) or Settings.from_env()
        resolved = validate_and_resolve_test_clock(request, settings)
        if resolved is not None:
            return resolved

    return get_now()
