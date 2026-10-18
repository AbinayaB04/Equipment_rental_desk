"""Tests for shared API foundation: error handling, request ID, logging, and test clock."""

from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core.clock import get_request_clock, parse_test_clock_header
from app.core.config import Settings
from app.core.middleware import REQUEST_ID_PATTERN, get_or_generate_request_id
from app.domain.exceptions import (
    EntityNotFoundError,
    InvalidLoanStateError,
    ItemNotAvailableError,
    MemberSuspendedError,
    OverpaymentError,
)
from app.main import create_app

# --- Router for Triggering Error and Clock Paths in Tests ---
foundation_router = APIRouter(prefix="/_test_foundation")


class SamplePayload(BaseModel):
    name: str = Field(..., min_length=2)
    amount: int = Field(..., gt=0)


@foundation_router.post("/validate")
def endpoint_validate(payload: SamplePayload) -> dict[str, str]:
    return {"message": f"Hello {payload.name}"}


@foundation_router.get("/domain/{error_type}")
def endpoint_domain_error(error_type: str) -> None:
    if error_type == "not_found":
        raise EntityNotFoundError("Item with ID 999 not found.")
    elif error_type == "suspended":
        raise MemberSuspendedError("Member 'Bob' is currently suspended.")
    elif error_type == "conflict":
        raise ItemNotAvailableError("Item 'Drill' is already reserved.")
    elif error_type == "invalid_state":
        raise InvalidLoanStateError("Cannot return loan #12 because it is not checked out.")
    elif error_type == "overpayment":
        raise OverpaymentError("Payment of ₹50.00 exceeds outstanding balance of ₹20.00.")
    raise ValueError(f"Unknown error type: {error_type}")


@foundation_router.get("/integrity")
def endpoint_integrity_error() -> None:
    # Simulate a PostgreSQL integrity error with sensitive internal SQL statements
    raise IntegrityError(
        statement="INSERT INTO members (id, secret_token) VALUES (1, 'sensitive_hash_xyz')",
        params={},
        orig=Exception("violates foreign key constraint 'fk_loans_member_id' on table 'loans'"),
    )


@foundation_router.get("/unexpected")
def endpoint_unexpected_error() -> None:
    # Simulate unexpected bug with sensitive internal exception text
    raise RuntimeError("Internal crash: database_connection_string='postgresql://admin:secret@db'")


@foundation_router.get("/clock")
def endpoint_clock(now: Annotated[datetime, Depends(get_request_clock)]) -> dict[str, str]:
    return {"now": now.isoformat()}


def make_test_client(
    app_env: str = "test",
    allow_test_clock: bool = True,
    test_clock_key: str = "",
    raise_server_exceptions: bool = True,
) -> TestClient:
    settings = Settings(
        app_env=app_env,
        database_url="",
        cors_origins=("http://localhost:5173",),
        log_level="INFO",
        allow_test_clock=allow_test_clock,
        test_clock_key=test_clock_key,
    )
    app: FastAPI = create_app(settings)
    app.include_router(foundation_router)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


# --- 1. Request Validation Tests ---


def test_validation_error_returns_safe_structured_response():
    client = make_test_client()
    response = client.post("/_test_foundation/validate", json={"name": "", "amount": -10})

    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "Unprocessable Entity"
    assert data["code"] == "VALIDATION_ERROR"
    assert "name" in data["detail"]
    assert "amount" in data["detail"]
    assert "request_id" in data
    assert response.headers.get("X-Request-ID") == data["request_id"]


# --- 2. Known Domain Exception Mapping Tests ---


@pytest.mark.parametrize(
    ("error_type", "expected_status", "expected_code", "expected_error"),
    [
        ("not_found", 404, "NOT_FOUND", "Not Found"),
        ("suspended", 403, "MEMBER_SUSPENDED", "Forbidden"),
        ("conflict", 409, "ITEM_NOT_AVAILABLE", "Conflict"),
        ("invalid_state", 409, "INVALID_LOAN_STATE", "Conflict"),
        ("overpayment", 400, "OVERPAYMENT", "Bad Request"),
    ],
)
def test_domain_error_mapping(error_type, expected_status, expected_code, expected_error):
    client = make_test_client()
    response = client.get(f"/_test_foundation/domain/{error_type}")

    assert response.status_code == expected_status
    data = response.json()
    assert data["error"] == expected_error
    assert data["code"] == expected_code
    assert len(data["detail"]) > 0
    assert "request_id" in data
    assert response.headers.get("X-Request-ID") == data["request_id"]


# --- 3. Database Integrity Conflict Tests (No SQL Leaked) ---


def test_integrity_error_does_not_leak_sql_or_driver_details():
    client = make_test_client()
    response = client.get("/_test_foundation/integrity")

    assert response.status_code == 409
    data = response.json()
    assert data["error"] == "Conflict"
    assert data["code"] == "DATABASE_CONFLICT"
    # Verify no internal SQL statements or secret values leaked to client
    assert "sensitive_hash_xyz" not in data["detail"]
    assert "INSERT INTO" not in data["detail"]
    assert "fk_loans_member_id" not in data["detail"]
    assert "operation conflicts" in data["detail"].lower()
    assert response.headers.get("X-Request-ID") == data["request_id"]


# --- 4. Unexpected Exception Handling Tests (No Traceback Leaked) ---


def test_unexpected_exception_returns_generic_500_without_leak():
    client = make_test_client(
        app_env="production",
        allow_test_clock=False,
        raise_server_exceptions=False,
    )
    response = client.get("/_test_foundation/unexpected")

    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "Internal Server Error"
    assert data["code"] == "INTERNAL_SERVER_ERROR"
    # Internal message and credentials must not be leaked
    assert "secret@db" not in data["detail"]
    assert "postgresql://" not in data["detail"]
    assert "crash" not in data["detail"]
    assert "unexpected error" in data["detail"].lower()
    assert response.headers.get("X-Request-ID") == data["request_id"]


# --- 5. Request ID Generation and Propagation Tests ---


def test_request_id_generated_when_missing():
    client = make_test_client()
    response = client.get("/health")

    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    assert len(req_id) >= 16


def test_request_id_propagated_when_valid():
    client = make_test_client()
    custom_id = "test-req-12345_ABC"
    response = client.get("/health", headers={"X-Request-ID": custom_id})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_request_id_sanitized_when_invalid_or_oversized():
    # Length > 64 chars or containing control/illegal characters
    malicious_id = "a" * 100
    chosen = get_or_generate_request_id(malicious_id)
    assert chosen != malicious_id
    assert len(chosen) == 36  # Standard UUID format

    illegal_chars = "bad<script>id\n"
    chosen_clean = get_or_generate_request_id(illegal_chars)
    assert chosen_clean != illegal_chars
    assert len(chosen_clean) == 36


def test_request_id_replaced_when_oversized_in_request():
    client = make_test_client()
    oversized_id = "X" * 128
    response = client.get("/health", headers={"X-Request-ID": oversized_id})

    assert response.status_code == 200
    returned_id = response.headers.get("X-Request-ID")
    assert returned_id is not None
    assert returned_id != oversized_id
    assert len(returned_id) == 36  # Standard UUID format
    assert REQUEST_ID_PATTERN.match(returned_id)


# --- 6. Reviewer Test Clock Tests ---


def test_test_clock_disabled_by_default_rejects_override():
    # When allow_test_clock is False, override attempt returns 403 Forbidden
    client = make_test_client(app_env="test", allow_test_clock=False)
    response = client.get(
        "/_test_foundation/clock",
        headers={"X-Test-Clock": "2026-10-25T14:00:00Z"},
    )

    assert response.status_code == 403
    data = response.json()
    assert data["code"] == "FORBIDDEN"
    assert "disabled" in data["detail"].lower()


def test_test_clock_cannot_be_activated_in_production():
    # Hard guard: Even if ALLOW_TEST_CLOCK=true in environment, APP_ENV=production blocks it
    prod_settings = Settings.from_env(
        {
            "APP_ENV": "production",
            "ALLOW_TEST_CLOCK": "true",
        }
    )
    assert prod_settings.allow_test_clock is False

    # Also test via client
    client = make_test_client(app_env="production", allow_test_clock=False)
    response = client.get(
        "/_test_foundation/clock",
        headers={"X-Test-Clock": "2026-10-25T14:00:00Z"},
    )
    assert response.status_code == 403


def test_test_clock_accepts_valid_utc_and_offset_timestamps():
    client = make_test_client(app_env="test", allow_test_clock=True)

    # 1. UTC timestamp ending in Z
    res1 = client.get(
        "/_test_foundation/clock",
        headers={"X-Test-Clock": "2026-10-25T14:00:00Z"},
    )
    assert res1.status_code == 200
    assert res1.json()["now"] == "2026-10-25T14:00:00+00:00"

    # 2. Offset timestamp (+05:30) converted to UTC
    # 19:30 in +05:30 is exactly 14:00:00 UTC
    res2 = client.get(
        "/_test_foundation/clock",
        headers={"X-Test-Clock": "2026-10-25T19:30:00+05:30"},
    )
    assert res2.status_code == 200
    assert res2.json()["now"] == "2026-10-25T14:00:00+00:00"


def test_test_clock_rejects_naive_and_malformed_timestamps():
    client = make_test_client(app_env="test", allow_test_clock=True)

    # Naive timestamp (no tz / Z)
    res_naive = client.get(
        "/_test_foundation/clock",
        headers={"X-Test-Clock": "2026-10-25T14:00:00"},
    )
    assert res_naive.status_code == 400
    assert "timezone-aware" in res_naive.json()["detail"].lower()

    # Malformed string
    res_bad = client.get(
        "/_test_foundation/clock",
        headers={"X-Test-Clock": "not-a-valid-timestamp"},
    )
    assert res_bad.status_code == 400
    assert "invalid" in res_bad.json()["detail"].lower()


def test_test_clock_enforces_key_authentication_when_configured():
    client = make_test_client(
        app_env="test",
        allow_test_clock=True,
        test_clock_key="super_secret_reviewer_key",
    )

    # Missing key -> 401 Unauthorized
    res_missing = client.get(
        "/_test_foundation/clock",
        headers={"X-Test-Clock": "2026-10-25T14:00:00Z"},
    )
    assert res_missing.status_code == 401
    assert "unauthorized" in res_missing.json()["error"].lower()

    # Wrong key -> 401 Unauthorized
    res_wrong = client.get(
        "/_test_foundation/clock",
        headers={
            "X-Test-Clock": "2026-10-25T14:00:00Z",
            "X-Test-Clock-Key": "incorrect_key",
        },
    )
    assert res_wrong.status_code == 401

    # Correct key -> 200 OK
    res_ok = client.get(
        "/_test_foundation/clock",
        headers={
            "X-Test-Clock": "2026-10-25T14:00:00Z",
            "X-Test-Clock-Key": "super_secret_reviewer_key",
        },
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["now"] == "2026-10-25T14:00:00+00:00"


def test_clock_falls_back_to_real_utc_when_no_override_header():
    client = make_test_client(app_env="test", allow_test_clock=True)
    before = datetime.now(UTC)
    response = client.get("/_test_foundation/clock")
    after = datetime.now(UTC)

    assert response.status_code == 200
    returned_time = datetime.fromisoformat(response.json()["now"])
    assert before <= returned_time <= after


def test_parse_test_clock_header_unit():
    # Direct unit tests for parse_test_clock_header
    with pytest.raises(ValueError, match="empty"):
        parse_test_clock_header("")

    with pytest.raises(ValueError, match="timezone-aware"):
        parse_test_clock_header("2026-10-18T12:00:00")

    parsed = parse_test_clock_header("2026-10-18T12:00:00Z")
    assert parsed.tzinfo == UTC
    assert parsed.hour == 12
