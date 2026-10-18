"""Focused API tests for Loan endpoints covering all lifecycle operations and boundary rules."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    """Test client with database session override."""
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield session
        session.commit()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# Helper functions
def create_member(client: TestClient, name="Alice", phone="+91-98765-00001") -> dict:
    return client.post("/members", json={"name": name, "phone": phone}).json()


def create_item(
    client: TestClient,
    name="Circular Saw",
    category="Saws",
    replacement_value=50000,
) -> dict:
    return client.post(
        "/items",
        json={"name": name, "category": category, "replacement_value": replacement_value},
    ).json()


# 1. Successful reservation
def test_reserve_loan_success(client: TestClient):
    """POST /loans/reserve creates a reservation in RESERVED status and returns 201."""
    member = create_member(client)
    item = create_item(client)

    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 201
    data = res.json()
    assert data["id"] > 0
    assert data["member_id"] == member["id"]
    assert data["item_id"] == item["id"]
    assert data["status"] == "RESERVED"
    assert data["fee_charged"] == 0
    assert data["checked_out_at"] is None

    # Check item status transitioned to RESERVED
    item_res = client.get(f"/items/{item['id']}")
    assert item_res.json()["status"] == "RESERVED"


# 2. Reservation of an unavailable item
def test_reserve_unavailable_item_rejected(client: TestClient):
    """POST /loans/reserve rejects reserving an item that is already reserved."""
    m1 = create_member(client, name="Alice", phone="+91-11111")
    m2 = create_member(client, name="Bob", phone="+91-22222")
    item = create_item(client)

    client.post("/loans/reserve", json={"member_id": m1["id"], "item_id": item["id"]})
    res = client.post("/loans/reserve", json={"member_id": m2["id"], "item_id": item["id"]})

    assert res.status_code == 409
    assert res.json()["code"] == "ITEM_NOT_AVAILABLE"


# 3. Reservation by a nonexistent member
def test_reserve_nonexistent_member_rejected(client: TestClient):
    """POST /loans/reserve returns 404 for a nonexistent member ID."""
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": 99999, "item_id": item["id"]})
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


# 4. Reservation of a nonexistent item
def test_reserve_nonexistent_item_rejected(client: TestClient):
    """POST /loans/reserve returns 404 for a nonexistent item ID."""
    member = create_member(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": 99999})
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


# 5. Reservation by a suspended member
def test_reserve_suspended_member_rejected(client: TestClient):
    """POST /loans/reserve returns 403 when the member is suspended."""
    member = create_member(client)
    item = create_item(client)
    client.post(f"/members/{member['id']}/suspend")

    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 403
    assert res.json()["code"] == "MEMBER_SUSPENDED"


# 6. Reservation with a fee balance exactly ₹100 (10,000 paise)
def test_reserve_exact_100_rupees_balance_permitted(client: TestClient, session: Session):
    """Member with unpaid balance of exactly ₹100 (10,000 paise) is permitted to borrow."""
    member_data = create_member(client)
    item_data = create_item(client)

    # Set balance to exactly 10,000 paise (₹100)
    db_member = session.get(Member, member_data["id"])
    db_member.running_fee_balance = 10000
    session.commit()

    res = client.post(
        "/loans/reserve",
        json={"member_id": member_data["id"], "item_id": item_data["id"]},
    )
    assert res.status_code == 201
    assert res.json()["status"] == "RESERVED"


# 7. Reservation with a fee balance of ₹100.01 (10,001 paise)
def test_reserve_over_100_rupees_balance_blocked(client: TestClient, session: Session):
    """Member with unpaid balance > ₹100 (10,001 paise) is blocked from borrowing."""
    member_data = create_member(client)
    item_data = create_item(client)

    # Set balance to 10,001 paise (₹100.01)
    db_member = session.get(Member, member_data["id"])
    db_member.running_fee_balance = 10001
    session.commit()

    res = client.post(
        "/loans/reserve",
        json={"member_id": member_data["id"], "item_id": item_data["id"]},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "BALANCE_LIMIT_EXCEEDED"


# 8. Reservation when member already has three active loans
def test_reserve_maximum_active_loans_exceeded(client: TestClient):
    """Member with 3 active loans is rejected from creating a 4th loan."""
    member = create_member(client)
    i1 = create_item(client, name="Item 1")
    i2 = create_item(client, name="Item 2")
    i3 = create_item(client, name="Item 3")
    i4 = create_item(client, name="Item 4")

    # Create 3 reservations
    assert (
        client.post(
            "/loans/reserve", json={"member_id": member["id"], "item_id": i1["id"]}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/loans/reserve", json={"member_id": member["id"], "item_id": i2["id"]}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/loans/reserve", json={"member_id": member["id"], "item_id": i3["id"]}
        ).status_code
        == 201
    )

    # 4th reservation is blocked
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": i4["id"]})
    assert res.status_code == 400
    assert res.json()["code"] == "ACTIVE_LOAN_LIMIT_EXCEEDED"


# 9. Reservation when member has a loan overdue by more than 14 days
def test_reserve_member_with_long_overdue_blocked(client: TestClient, session: Session):
    """Member with a loan overdue > 14 days cannot borrow."""
    now = datetime.now(UTC)
    member_data = create_member(client)
    i1 = create_item(client, name="Old Item")
    i2 = create_item(client, name="New Item")

    # Manually inject an overdue loan: due 16 days ago (> 14 days)
    overdue_loan = Loan(
        member_id=member_data["id"],
        item_id=i1["id"],
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(days=25),
        checked_out_at=now - timedelta(days=23),
        due_at=now - timedelta(days=16),
        fee_charged=0,
    )
    session.add(overdue_loan)
    session.commit()

    res = client.post(
        "/loans/reserve",
        json={"member_id": member_data["id"], "item_id": i2["id"]},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "OVERDUE_RESTRICTION"


# 10. Reservation expiry at documented 48-hour boundary
def test_reservation_expiry_boundary(client: TestClient, session: Session):
    """At 47h59m reservation is unexpired; at exact 48h it is expired and checkout fails."""
    t0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    member = create_member(client)
    item = create_item(client)

    # Create reservation backdated to t0
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]

    db_loan = session.get(Loan, loan_id)
    db_loan.reserved_at = t0
    session.commit()

    # Settle at 47h 59m: unexpired
    from app.services.loan_service import LoanService

    _, was_expired = LoanService.settle_expired_reservation(
        session, loan_id=loan_id, now=t0 + timedelta(hours=47, minutes=59)
    )
    assert was_expired is False

    # Settle at exact 48h: expired
    settled_loan, was_expired_48 = LoanService.settle_expired_reservation(
        session, loan_id=loan_id, now=t0 + timedelta(hours=48)
    )
    assert was_expired_48 is True
    assert settled_loan.status == LoanStatus.CANCELLED


# 11. Successful checkout and correct seven-day due date
def test_checkout_loan_success(client: TestClient):
    """POST /loans/{id}/checkout sets CHECKED_OUT status and due date 7 days after checkout."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]

    co_res = client.post(f"/loans/{loan_id}/checkout")
    assert co_res.status_code == 200
    data = co_res.json()
    assert data["status"] == "CHECKED_OUT"
    assert data["checked_out_at"] is not None
    assert data["due_at"] is not None

    co_dt = datetime.fromisoformat(data["checked_out_at"])
    due_dt = datetime.fromisoformat(data["due_at"])
    # Due date is exactly 7 days after checkout
    assert due_dt - co_dt == timedelta(days=7)

    # Item status transitioned to CHECKED_OUT
    item_res = client.get(f"/items/{item['id']}")
    assert item_res.json()["status"] == "CHECKED_OUT"


# 12. Checkout of an expired reservation
def test_checkout_expired_reservation_committed_and_returns_400(
    client: TestClient, session: Session
):
    """POST /loans/{id}/checkout on expired reservation commits cancellation and returns 400."""
    t0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]

    # Backdate reservation by 50 hours
    db_loan = session.get(Loan, loan_id)
    db_loan.reserved_at = t0
    session.commit()

    # Attempt checkout at t0 + 50h via service outcome or current real time
    # (Since t0 is in 2026/10/01 and current real time > t0 + 48h, it is definitely expired)
    co_res = client.post(f"/loans/{loan_id}/checkout")
    assert co_res.status_code == 400
    data = co_res.json()
    assert data["code"] == "RESERVATION_EXPIRED"
    assert "expired" in data["detail"].lower()

    # Verify committed state: loan is CANCELLED and item is AVAILABLE
    session.expire_all()
    fresh_loan = session.get(Loan, loan_id)
    assert fresh_loan.status == LoanStatus.CANCELLED
    fresh_item = session.get(Item, item["id"])
    assert fresh_item.status == ItemStatus.AVAILABLE


# 13. Duplicate checkout
def test_duplicate_checkout_rejected(client: TestClient):
    """POST /loans/{id}/checkout on already checked-out loan returns 409 INVALID_LOAN_STATE."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]

    assert client.post(f"/loans/{loan_id}/checkout").status_code == 200

    dup_res = client.post(f"/loans/{loan_id}/checkout")
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "INVALID_LOAN_STATE"


# 14. Successful return with no late fee
def test_return_loan_on_time_zero_fee(client: TestClient):
    """POST /loans/{id}/return on time returns 200 with fee_charged=0 and restores item."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]
    client.post(f"/loans/{loan_id}/checkout")

    ret_res = client.post(f"/loans/{loan_id}/return")
    assert ret_res.status_code == 200
    data = ret_res.json()
    assert data["status"] == "RETURNED"
    assert data["fee_charged"] == 0
    assert data["returned_at"] is not None

    # Item is restored to AVAILABLE
    item_res = client.get(f"/items/{item['id']}")
    assert item_res.json()["status"] == "AVAILABLE"


# 15. Return with a late fee
def test_return_loan_with_late_fee(client: TestClient, session: Session):
    """POST /loans/{id}/return overdue assesses ₹10/day late fee and updates member balance."""
    member_data = create_member(client)
    item_data = create_item(client)
    loan_id = client.post(
        "/loans/reserve",
        json={"member_id": member_data["id"], "item_id": item_data["id"]},
    ).json()["id"]
    client.post(f"/loans/{loan_id}/checkout")

    # Backdate checkout to 10 days ago (due 2.5 days ago -> rounds up to 3 calendar days)
    # 3 days late -> 3 * ₹10 = ₹30 = 3000 paise
    now = datetime.now(UTC)
    db_loan = session.get(Loan, loan_id)
    db_loan.checked_out_at = now - timedelta(days=10)
    db_loan.due_at = now - timedelta(days=2, hours=12)
    session.commit()

    ret_res = client.post(f"/loans/{loan_id}/return")
    assert ret_res.status_code == 200
    assert ret_res.json()["fee_charged"] == 3000

    # Verify member running_fee_balance incremented
    member_res = client.get(f"/members/{member_data['id']}")
    assert member_res.json()["running_fee_balance"] == 3000


# 16. Late-fee cap at ₹200 (20,000 paise)
def test_return_loan_fee_capped_at_200_rupees(client: TestClient, session: Session):
    """Late fee is capped at ₹200 (20,000 paise) even after 30 days overdue."""
    member_data = create_member(client)
    item_data = create_item(client, replacement_value=100000)  # ₹1000 > ₹200
    loan_id = client.post(
        "/loans/reserve",
        json={"member_id": member_data["id"], "item_id": item_data["id"]},
    ).json()["id"]
    client.post(f"/loans/{loan_id}/checkout")

    # 30 days overdue (would be ₹300 uncapped)
    now = datetime.now(UTC)
    db_loan = session.get(Loan, loan_id)
    db_loan.checked_out_at = now - timedelta(days=37)
    db_loan.due_at = now - timedelta(days=30)
    session.commit()

    ret_res = client.post(f"/loans/{loan_id}/return")
    assert ret_res.status_code == 200
    assert ret_res.json()["fee_charged"] == 20000  # Exactly ₹200


# 17. Late fee capped by replacement value
def test_return_loan_fee_capped_by_replacement_value(client: TestClient, session: Session):
    """Late fee cannot exceed item replacement value when replacement value < ₹200."""
    member_data = create_member(client)
    item_data = create_item(client, replacement_value=8000)  # ₹80 < ₹200 cap
    loan_id = client.post(
        "/loans/reserve",
        json={"member_id": member_data["id"], "item_id": item_data["id"]},
    ).json()["id"]
    client.post(f"/loans/{loan_id}/checkout")

    # 15 days overdue (would be ₹150, but replacement value is ₹80)
    now = datetime.now(UTC)
    db_loan = session.get(Loan, loan_id)
    db_loan.checked_out_at = now - timedelta(days=22)
    db_loan.due_at = now - timedelta(days=15)
    session.commit()

    ret_res = client.post(f"/loans/{loan_id}/return")
    assert ret_res.status_code == 200
    assert ret_res.json()["fee_charged"] == 8000  # Capped at ₹80


# 18. Return of a reserved but never checked-out loan
def test_return_reserved_loan_rejected(client: TestClient):
    """POST /loans/{id}/return on a RESERVED loan returns 409 INVALID_LOAN_STATE."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]

    res = client.post(f"/loans/{loan_id}/return")
    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_LOAN_STATE"


# 19. Duplicate return
def test_duplicate_return_rejected(client: TestClient):
    """POST /loans/{id}/return on an already RETURNED loan returns 409 INVALID_LOAN_STATE."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]
    client.post(f"/loans/{loan_id}/checkout")
    assert client.post(f"/loans/{loan_id}/return").status_code == 200

    dup_res = client.post(f"/loans/{loan_id}/return")
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "INVALID_LOAN_STATE"


# 20. Successful reservation cancellation
def test_cancel_reservation_success(client: TestClient):
    """POST /loans/{id}/cancel cancels pending reservation and restores item to AVAILABLE."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]

    cancel_res = client.post(f"/loans/{loan_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"
    assert cancel_res.json()["cancelled_at"] is not None

    # Item restored to AVAILABLE
    item_res = client.get(f"/items/{item['id']}")
    assert item_res.json()["status"] == "AVAILABLE"


# 21. Cancellation of a checked-out, expired, or already-cancelled reservation
def test_cancel_invalid_state_rejected(client: TestClient):
    """POST /loans/{id}/cancel on checked-out or already cancelled loan returns 409."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    loan_id = res.json()["id"]

    # Check out the loan
    client.post(f"/loans/{loan_id}/checkout")

    # Cannot cancel checked out loan
    res1 = client.post(f"/loans/{loan_id}/cancel")
    assert res1.status_code == 409
    assert res1.json()["code"] == "INVALID_LOAN_STATE"

    # Now create another reservation and cancel it twice
    i2 = create_item(client, name="Item B")
    r2 = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": i2["id"]})
    l2_id = r2.json()["id"]
    assert client.post(f"/loans/{l2_id}/cancel").status_code == 200

    # Duplicate cancel
    res2 = client.post(f"/loans/{l2_id}/cancel")
    assert res2.status_code == 409
    assert res2.json()["code"] == "INVALID_LOAN_STATE"


# 22. Invalid loan ID handling
def test_loan_not_found(client: TestClient):
    """GET /loans/99999 returns 404 with structured NOT_FOUND error."""
    res = client.get("/loans/99999")
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


# 23. Test-clock behavior
def test_test_clock_behavior(client: TestClient):
    """Request with X-Test-Clock header stamps the exact timestamp on reservation."""
    from app.core.config import Settings

    app = client.app
    app.state.settings = Settings(
        app_env="development",
        database_url="",
        cors_origins=(),
        log_level="INFO",
        allow_test_clock=True,
    )

    member = create_member(client)
    item = create_item(client)

    test_time = "2026-10-25T14:30:00Z"
    res = client.post(
        "/loans/reserve",
        json={"member_id": member["id"], "item_id": item["id"]},
        headers={"X-Test-Clock": test_time},
    )
    assert res.status_code == 201
    assert res.json()["reserved_at"].startswith("2026-10-25T14:30:00")


# 24. Transaction rollback when an operation fails
def test_transaction_rollback_on_failed_reservation(client: TestClient, session: Session):
    """Failed reservation rolls back item status cleanly."""
    member = create_member(client)
    item = create_item(client)
    client.post(f"/members/{member['id']}/suspend")

    # Reserve by suspended member should fail and not alter item or create loan
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 403

    item_res = client.get(f"/items/{item['id']}")
    assert item_res.json()["status"] == "AVAILABLE"
    assert len(client.get("/loans").json()) == 0


# Listing and filtering loans
def test_list_loans_and_aliases(client: TestClient):
    """GET /loans supports filtering and /api/loans alias works."""
    m1 = create_member(client, name="M1", phone="+91-1")
    m2 = create_member(client, name="M2", phone="+91-2")
    i1 = create_item(client, name="I1")
    i2 = create_item(client, name="I2")

    l1 = client.post("/loans/reserve", json={"member_id": m1["id"], "item_id": i1["id"]}).json()
    l2 = client.post("/loans/reserve", json={"member_id": m2["id"], "item_id": i2["id"]}).json()
    client.post(f"/loans/{l2['id']}/checkout")

    # Filter by member
    res_m1 = client.get(f"/loans?member_id={m1['id']}")
    assert res_m1.status_code == 200
    ids_m1 = [loan["id"] for loan in res_m1.json()]
    assert l1["id"] in ids_m1
    assert l2["id"] not in ids_m1

    # Filter by status
    res_co = client.get("/loans?status=CHECKED_OUT")
    assert res_co.status_code == 200
    ids_co = [loan["id"] for loan in res_co.json()]
    assert l2["id"] in ids_co
    assert l1["id"] not in ids_co

    # Prefix alias /api/loans
    res_alias = client.get(f"/api/loans/{l1['id']}")
    assert res_alias.status_code == 200
    assert res_alias.json()["id"] == l1["id"]
