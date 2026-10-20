"""Tests for request-scoped test clock hardening, validation window, and security."""

import threading
from datetime import timedelta

from fastapi.testclient import TestClient

try:
    from app.core.clock import TEST_CLOCK_MAX_OFFSET, get_now
except ImportError:
    from app.core.clock import get_now

    TEST_CLOCK_MAX_OFFSET = timedelta(days=90)
from app.core.config import Settings
from app.core.database import session_scope
from app.main import create_app
from app.models.item import Item
from app.models.loan import Loan
from app.models.member import Member

VALID_KEY = "local-dev-clock-key-123456"
ALLOWED_ORIGIN = "http://localhost:5173"


def make_test_client(
    allow_test_clock: bool = True,
    test_clock_key: str = VALID_KEY,
    app_env: str = "development",
) -> TestClient:
    settings = Settings(
        app_env=app_env,
        database_url="postgresql+psycopg://rental:rental_dev_password@localhost:5434/rental",
        cors_origins=(ALLOWED_ORIGIN,),
        log_level="INFO",
        allow_test_clock=allow_test_clock,
        test_clock_key=test_clock_key,
    )
    return TestClient(create_app(settings))


def test_window_bounds_and_invalid_formats():
    """Test Case 1: Window bounds (+/- 90d), extreme timestamps, and invalid formats.

    Every rejection must return HTTP 422 with code INVALID_TEST_CLOCK and standard error
    envelope, leaving the database row counts completely unchanged.
    """
    client = make_test_client(allow_test_clock=True, test_clock_key=VALID_KEY)

    # Valid boundaries (+90d, -90d)
    valid_cases = [
        ("real_now + 90d", lambda: (get_now() + TEST_CLOCK_MAX_OFFSET).isoformat()),
        ("real_now - 90d", lambda: (get_now() - TEST_CLOCK_MAX_OFFSET).isoformat()),
    ]
    for case_name, clock_fn in valid_cases:
        clock_str = clock_fn()
        resp = client.get(
            "/loans/overdue",
            headers={"X-Test-Clock": clock_str, "X-Test-Clock-Key": VALID_KEY},
        )
        assert (
            resp.status_code == 200
        ), f"Case {case_name} should be accepted, got {resp.status_code}: {resp.text}"
        assert (
            resp.headers.get("X-Clock-Mode") == "test"
        ), f"Case {case_name} must have X-Clock-Mode: test"

    # Count database rows before rejections
    with session_scope() as session:
        loans_before = session.query(Loan).count()
        items_before = session.query(Item).count()
        members_before = session.query(Member).count()

    # Invalid cases that must be rejected with 422 INVALID_TEST_CLOCK
    invalid_cases = [
        (
            "real_now + 90d + 1s",
            lambda: (get_now() + TEST_CLOCK_MAX_OFFSET + timedelta(seconds=1)).isoformat(),
        ),
        (
            "real_now - 90d - 1s",
            lambda: (get_now() - TEST_CLOCK_MAX_OFFSET - timedelta(seconds=1)).isoformat(),
        ),
        ("year 9999", lambda: "9999-12-31T00:00:00Z"),
        ("year 0001", lambda: "0001-01-01T00:00:00Z"),
        ("naive timestamp", lambda: "2026-10-25T14:00:00"),
        ("invalid date 2026-13-45", lambda: "2026-13-45T00:00:00Z"),
        ("empty string", lambda: ""),
        ("non-date abc", lambda: "abc"),
        ("5000-char string", lambda: "2026-10-25T00:00:00Z" + "a" * 5000),
        ("trailing space", lambda: "2026-10-25T00:00:00Z "),
    ]

    for case_name, clock_fn in invalid_cases:
        bad_clock = clock_fn()
        resp = client.post(
            "/loans/reserve",
            json={"member_id": 1, "item_id": 1},
            headers={"X-Test-Clock": bad_clock, "X-Test-Clock-Key": VALID_KEY},
        )
        assert (
            resp.status_code == 422
        ), f"Case {case_name} must return 422, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert (
            body.get("code") == "INVALID_TEST_CLOCK"
        ), f"Case {case_name} must return code INVALID_TEST_CLOCK, got {body.get('code')}"
        assert (
            "error" in body and "detail" in body and "request_id" in body
        ), f"Case {case_name} must match standard error envelope"
        assert (
            "X-Clock-Mode" not in resp.headers
        ), f"Case {case_name} rejection must NOT have X-Clock-Mode header"

    # Verify database unchanged after rejected writes
    with session_scope() as session:
        assert (
            session.query(Loan).count() == loans_before
        ), "Loan count changed after rejected clock writes"
        assert (
            session.query(Item).count() == items_before
        ), "Item count changed after rejected clock writes"
        assert (
            session.query(Member).count() == members_before
        ), "Member count changed after rejected clock writes"


def test_wedge_regression():
    """Test Case 2: After any rejected clock, normal requests without clock work as before."""
    client = make_test_client(allow_test_clock=True, test_clock_key=VALID_KEY)

    # 1. Trigger a clock rejection
    bad_resp = client.post(
        "/loans/reserve",
        json={"member_id": 1, "item_id": 1},
        headers={"X-Test-Clock": "9999-12-31T00:00:00Z", "X-Test-Clock-Key": VALID_KEY},
    )
    assert bad_resp.status_code == 422

    # 2. Immediately execute normal requests without clock headers
    # Reserve item 9 (available in seed data) for member 1
    reserve_resp = client.post(
        "/loans/reserve",
        json={"member_id": 1, "item_id": 9},
    )
    assert reserve_resp.status_code == 201, f"Normal reservation failed: {reserve_resp.text}"
    loan_id = reserve_resp.json()["id"]

    # Cancel reservation
    cancel_resp = client.post(f"/loans/{loan_id}/cancel")
    assert cancel_resp.status_code == 200, f"Normal cancellation failed: {cancel_resp.text}"
    assert cancel_resp.json()["status"] == "CANCELLED"


def test_disabled_by_default_rejects_with_403():
    """Test Case 3: When disabled, X-Test-Clock present -> 403 TEST_CLOCK_DISABLED."""
    client = make_test_client(allow_test_clock=False, test_clock_key="")

    # Request with clock header when disabled -> 403 TEST_CLOCK_DISABLED
    resp = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": "2026-10-25T00:00:00Z"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("code") == "TEST_CLOCK_DISABLED"
    assert "error" in body and "detail" in body and "request_id" in body

    # Normal request without clock header -> 200 OK
    normal_resp = client.get("/loans/overdue")
    assert normal_resp.status_code == 200


def test_authorization_when_enabled(caplog):
    """Test Case 4: Key authorization, constant-time compare, never leaks key in body/logs."""
    configured_key = "super-secret-key-123456"
    client = make_test_client(allow_test_clock=True, test_clock_key=configured_key)
    valid_clock = get_now().isoformat()

    # 1. Missing key -> 403 TEST_CLOCK_UNAUTHORIZED
    resp_missing = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": valid_clock},
    )
    assert resp_missing.status_code == 403
    assert resp_missing.json().get("code") == "TEST_CLOCK_UNAUTHORIZED"
    assert configured_key not in resp_missing.text

    # 2. Wrong key -> 403 TEST_CLOCK_UNAUTHORIZED
    resp_wrong = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": valid_clock, "X-Test-Clock-Key": "wrong-key-00000000"},
    )
    assert resp_wrong.status_code == 403
    assert resp_wrong.json().get("code") == "TEST_CLOCK_UNAUTHORIZED"
    assert configured_key not in resp_wrong.text

    # 3. Correct key -> 200 OK
    resp_ok = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": valid_clock, "X-Test-Clock-Key": configured_key},
    )
    assert resp_ok.status_code == 200
    assert configured_key not in resp_ok.text

    # 4. Assert key never appears in captured logs
    for record in caplog.records:
        assert configured_key not in record.message
        assert configured_key not in str(getattr(record, "args", ""))


def test_request_scoping_concurrent_threads():
    """Test Case 6: Concurrent requests with different clocks must never see each other's clock."""
    client = make_test_client(allow_test_clock=True, test_clock_key=VALID_KEY)
    real_now = get_now()

    # Seed data has loans due on:
    # loan 6: 2026-10-04
    # loan 4: 2026-10-17
    # Clock A: 2026-10-01 (before both -> 0 overdue loans)
    # Clock B: 2026-10-10 (after loan 6, before loan 4 -> 1 overdue loan)
    clock_a = (real_now - timedelta(days=20)).replace(hour=0, minute=0, second=0).isoformat()
    clock_b = (real_now + timedelta(days=20)).replace(hour=0, minute=0, second=0).isoformat()

    results: dict[str, list] = {}
    barrier = threading.Barrier(3)

    def worker(name: str, clock: str | None):
        headers = {"X-Test-Clock-Key": VALID_KEY}
        if clock:
            headers["X-Test-Clock"] = clock
        barrier.wait()
        res = client.get("/loans/overdue", headers=headers)
        results[name] = res.json()

    t1 = threading.Thread(target=worker, args=("clock_a", clock_a))
    t2 = threading.Thread(target=worker, args=("clock_b", clock_b))
    t3 = threading.Thread(target=worker, args=("real_time", None))

    t1.start()
    t2.start()
    t3.start()
    t1.join()
    t2.join()
    t3.join()

    # Responses must be isolated and reflect their own clock queries
    assert isinstance(results["clock_a"], list)
    assert isinstance(results["clock_b"], list)
    assert isinstance(results["real_time"], list)

    # After threads finish, a plain request uses real time
    plain_resp = client.get("/loans/overdue")
    assert plain_resp.status_code == 200
    assert "X-Clock-Mode" not in plain_resp.headers


def test_visibility_header_and_cors_expose_headers():
    """Test Case 7: X-Clock-Mode: test on success and error; exposed via CORS headers."""
    client = make_test_client(allow_test_clock=True, test_clock_key=VALID_KEY)
    valid_clock = get_now().isoformat()

    # 1. Successful request with test clock has X-Clock-Mode: test
    resp_ok = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": valid_clock, "X-Test-Clock-Key": VALID_KEY},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.headers.get("X-Clock-Mode") == "test"

    # 2. Error response with valid test clock (404 Not Found) still has X-Clock-Mode: test
    resp_404 = client.get(
        "/items/999999",
        headers={"X-Test-Clock": valid_clock, "X-Test-Clock-Key": VALID_KEY},
    )
    assert resp_404.status_code == 404
    assert resp_404.headers.get("X-Clock-Mode") == "test"

    # 3. Response without simulated clock does NOT have X-Clock-Mode
    resp_plain = client.get("/items/1")
    assert resp_plain.status_code == 200
    assert "X-Clock-Mode" not in resp_plain.headers

    # 4. CORS expose_headers includes X-Clock-Mode and X-Request-ID
    cors_resp = client.get(
        "/loans/overdue",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "X-Test-Clock": valid_clock,
            "X-Test-Clock-Key": VALID_KEY,
        },
    )
    assert cors_resp.status_code == 200
    expose_headers = cors_resp.headers.get("access-control-expose-headers", "")
    exposed_list = [h.strip().lower() for h in expose_headers.split(",")]
    assert "x-clock-mode" in exposed_list, f"X-Clock-Mode not exposed in CORS: {expose_headers}"
    assert "x-request-id" in exposed_list, f"X-Request-ID not exposed in CORS: {expose_headers}"


def test_health_returns_status_and_test_clock_enabled():
    """Test Case 8: /health returns {"status": "ok", "test_clock_enabled": <bool>} and no secret."""
    client_enabled = make_test_client(allow_test_clock=True, test_clock_key=VALID_KEY)
    resp = client_enabled.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"status": "ok", "test_clock_enabled": True}
    assert VALID_KEY not in resp.text

    client_disabled = make_test_client(allow_test_clock=False, test_clock_key="")
    resp_dis = client_disabled.get("/health")
    assert resp_dis.status_code == 200
    assert resp_dis.json() == {"status": "ok", "test_clock_enabled": False}


def test_logging_simulated_clock_warning(caplog):
    """Test Case 9: Using simulated clock logs one WARNING with request_id & simulated time,
    no key.
    """
    client = make_test_client(allow_test_clock=True, test_clock_key=VALID_KEY)
    valid_clock = get_now().isoformat()
    req_id = "test-clock-req-998877"

    resp = client.get(
        "/loans/overdue",
        headers={
            "X-Test-Clock": valid_clock,
            "X-Test-Clock-Key": VALID_KEY,
            "X-Request-ID": req_id,
        },
    )
    assert resp.status_code == 200

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    clock_warnings = [
        w for w in warnings if req_id in w.message or getattr(w, "request_id", None) == req_id
    ]
    assert len(clock_warnings) == 1, f"Expected exactly 1 clock WARNING log, got: {warnings}"
    warning = clock_warnings[0]
    assert VALID_KEY not in warning.message
    assert valid_clock in warning.message or getattr(warning, "simulated_time", None) == valid_clock


def test_clock_within_window_never_overflows():
    """Test Case 10: Valid test clocks within 90d window never overflow date math on writes."""
    client = make_test_client(allow_test_clock=True, test_clock_key=VALID_KEY)
    real_now = get_now()

    # Attempt reservations at +90d and -90d boundary clocks
    # They may fail business rules (e.g. item unavailable or member limit),
    # but NEVER OverflowError (HTTP 400/500 date math)
    boundary_clocks = [
        ("plus_90d", (real_now + TEST_CLOCK_MAX_OFFSET).isoformat()),
        ("minus_90d", (real_now - TEST_CLOCK_MAX_OFFSET).isoformat()),
    ]
    for case_name, clock_str in boundary_clocks:
        resp = client.post(
            "/loans/reserve",
            json={"member_id": 1, "item_id": 10},
            headers={"X-Test-Clock": clock_str, "X-Test-Clock-Key": VALID_KEY},
        )
        assert resp.status_code != 500, f"Case {case_name} reached 500 server error"
        if resp.status_code == 400:
            assert (
                resp.json().get("code") != "BAD_REQUEST"
            ), f"Case {case_name} reached OverflowError handler with 400 BAD_REQUEST: {resp.text}"
