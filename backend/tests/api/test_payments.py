"""Focused API tests for Payment and Member Statement endpoints."""

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
from app.models.payment import Payment


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


def create_test_member(client: TestClient, balance: int = 0, name: str = "Test Member") -> dict:
    """Helper to create a member via API."""
    res = client.post("/members", json={"name": name, "phone": "+91-98765-00000"})
    assert res.status_code == 201
    return res.json()


# ============================================================================
# Payment API Tests (POST /members/{id}/payments)
# ============================================================================


def test_record_payment_success(client: TestClient, session: Session):
    """POST /members/{id}/payments records payment and deducts member fee balance."""
    member_data = create_test_member(client)
    member_id = member_data["id"]

    # Set member balance to 5000 paise (₹50)
    db_member = session.get(Member, member_id)
    db_member.running_fee_balance = 5000
    session.commit()

    # Pay 2000 paise (₹20)
    res = client.post(
        f"/members/{member_id}/payments",
        json={"amount_paise": 2000, "note": "Partial payment"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] is not None
    assert data["member_id"] == member_id
    assert data["amount"] == 2000
    assert data["amount_paise"] == 2000
    assert data["note"] == "Partial payment"
    assert data["paid_at"] is not None

    # Check updated member balance: ₹50 - ₹20 = ₹30 (3000 paise)
    m_res = client.get(f"/members/{member_id}")
    assert m_res.status_code == 200
    assert m_res.json()["running_fee_balance"] == 3000


def test_record_payment_exact_balance_payoff(client: TestClient, session: Session):
    """Paying exact outstanding balance clears fee balance to zero."""
    member_data = create_test_member(client)
    member_id = member_data["id"]

    db_member = session.get(Member, member_id)
    db_member.running_fee_balance = 3000
    session.commit()

    res = client.post(f"/members/{member_id}/payments", json={"amount_paise": 3000})
    assert res.status_code == 201
    assert res.json()["amount"] == 3000

    m_res = client.get(f"/members/{member_id}")
    assert m_res.json()["running_fee_balance"] == 0


def test_record_payment_respects_test_clock(client: TestClient, session: Session):
    """Payment timestamp matches the X-Test-Clock header."""
    from app.core.config import Settings

    app = client.app
    app.state.settings = Settings(
        app_env="development",
        database_url="",
        cors_origins=(),
        log_level="INFO",
        allow_test_clock=True,
    )

    member_data = create_test_member(client)
    member_id = member_data["id"]

    db_member = session.get(Member, member_id)
    db_member.running_fee_balance = 2000
    session.commit()

    test_time = "2026-10-25T14:30:00Z"
    res = client.post(
        f"/members/{member_id}/payments",
        json={"amount_paise": 1000},
        headers={"X-Test-Clock": test_time},
    )
    assert res.status_code == 201
    assert res.json()["paid_at"].startswith("2026-10-25T14:30:00")


def test_record_payment_zero_amount_rejected(client: TestClient):
    """Zero payment amount is rejected with 422 VALIDATION_ERROR."""
    member_data = create_test_member(client)
    res = client.post(f"/members/{member_data['id']}/payments", json={"amount_paise": 0})
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"


def test_record_payment_negative_amount_rejected(client: TestClient):
    """Negative payment amount is rejected with 422 VALIDATION_ERROR."""
    member_data = create_test_member(client)
    res = client.post(f"/members/{member_data['id']}/payments", json={"amount_paise": -500})
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"


def test_record_payment_missing_member_returns_404(client: TestClient):
    """Payment for nonexistent member returns 404 NOT_FOUND."""
    res = client.post("/members/999999/payments", json={"amount_paise": 1000})
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_record_payment_unknown_fields_rejected(client: TestClient):
    """Unknown fields in payment request are rejected with 422."""
    member_data = create_test_member(client)
    res = client.post(
        f"/members/{member_data['id']}/payments",
        json={"amount_paise": 1000, "currency": "INR"},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"


def test_record_payment_optional_notes_handling(client: TestClient, session: Session):
    """Whitespace-only note is stripped to None, valid note is saved, omitted note is None."""
    member_data = create_test_member(client)
    member_id = member_data["id"]

    db_member = session.get(Member, member_id)
    db_member.running_fee_balance = 5000
    session.commit()

    # Note omitted -> None
    r1 = client.post(f"/members/{member_id}/payments", json={"amount_paise": 1000})
    assert r1.status_code == 201
    assert r1.json()["note"] is None

    # Whitespace-only note -> None
    r2 = client.post(f"/members/{member_id}/payments", json={"amount_paise": 1000, "note": "   "})
    assert r2.status_code == 201
    assert r2.json()["note"] is None

    # Normal note -> stripped note string
    r3 = client.post(
        f"/members/{member_id}/payments",
        json={"amount_paise": 1000, "note": " Cash paid "},
    )
    assert r3.status_code == 201
    assert r3.json()["note"] == "Cash paid"


def test_record_payment_overpayment_rejected_leaves_balance_intact(
    client: TestClient, session: Session
):
    """Payment exceeding balance returns 400 OVERPAYMENT and leaves balance unchanged."""
    member_data = create_test_member(client)
    member_id = member_data["id"]

    db_member = session.get(Member, member_id)
    db_member.running_fee_balance = 2000  # ₹20
    session.commit()

    # Try to pay ₹25 (2500 paise)
    res = client.post(f"/members/{member_id}/payments", json={"amount_paise": 2500})
    assert res.status_code == 400
    assert res.json()["code"] == "OVERPAYMENT"

    # Balance remains ₹20
    m_res = client.get(f"/members/{member_id}")
    assert m_res.json()["running_fee_balance"] == 2000

    # No payment was recorded
    session.expire_all()
    payments = session.query(Payment).filter(Payment.member_id == member_id).all()
    assert len(payments) == 0


def test_record_payment_suspended_member_can_pay(client: TestClient, session: Session):
    """Suspended members can pay down their fee balance to clear debt."""
    member_data = create_test_member(client)
    member_id = member_data["id"]

    # Suspend member and set balance
    client.post(f"/members/{member_id}/suspend")
    db_member = session.get(Member, member_id)
    db_member.running_fee_balance = 3000
    session.commit()

    res = client.post(f"/members/{member_id}/payments", json={"amount_paise": 1000})
    assert res.status_code == 201
    assert res.json()["amount"] == 1000

    m_res = client.get(f"/members/{member_id}")
    assert m_res.json()["status"] == "SUSPENDED"
    assert m_res.json()["running_fee_balance"] == 2000


def test_payment_api_alias_parity(client: TestClient, session: Session):
    """POST /api/members/{id}/payments works identically to /members/{id}/payments."""
    member_data = create_test_member(client)
    member_id = member_data["id"]

    db_member = session.get(Member, member_id)
    db_member.running_fee_balance = 2000
    session.commit()

    res = client.post(f"/api/members/{member_id}/payments", json={"amount_paise": 1000})
    assert res.status_code == 201
    assert res.json()["amount"] == 1000


# ============================================================================
# Member Statement API Tests (GET /members/{id}/statement)
# ============================================================================


def test_get_member_statement_success(client: TestClient, session: Session):
    """GET /members/{id}/statement returns member, loans, payments, and correct totals."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member_data = create_test_member(client)
    member_id = member_data["id"]

    # Create an item
    item = Item(
        name="Test Ladder",
        category="Ladders",
        replacement_value=15000,
        status=ItemStatus.AVAILABLE,
    )
    session.add(item)
    session.flush()

    # Add a returned loan with fee
    l1 = Loan(
        member_id=member_id,
        item_id=item.id,
        status=LoanStatus.RETURNED,
        reserved_at=now,
        checked_out_at=now,
        due_at=now + timedelta(days=7),
        returned_at=now + timedelta(days=10),
        fee_charged=3000,
    )
    # Add an active checked out loan with 0 fee
    l2 = Loan(
        member_id=member_id,
        item_id=item.id,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now + timedelta(days=1),
        checked_out_at=now + timedelta(days=1),
        due_at=now + timedelta(days=8),
        fee_charged=0,
    )
    # Add a cancelled reservation
    l3 = Loan(
        member_id=member_id,
        item_id=item.id,
        status=LoanStatus.CANCELLED,
        reserved_at=now + timedelta(days=2),
        cancelled_at=now + timedelta(days=2, hours=1),
        fee_charged=0,
    )
    session.add_all([l1, l2, l3])

    # Add payments
    p1 = Payment(
        member_id=member_id, amount=1000, paid_at=now + timedelta(days=11), note="First pay"
    )
    p2 = Payment(
        member_id=member_id, amount=500, paid_at=now + timedelta(days=12), note="Second pay"
    )
    session.add_all([p1, p2])

    # Member balance is 3000 fee - 1500 paid = 1500
    db_m = session.get(Member, member_id)
    db_m.running_fee_balance = 1500
    session.commit()

    res = client.get(f"/members/{member_id}/statement")
    assert res.status_code == 200
    data = res.json()

    assert data["member_id"] == member_id
    assert data["member"]["id"] == member_id
    assert data["member"]["name"] == member_data["name"]

    # Verify loans: all 3 present, ordered newest first (l3, l2, l1)
    assert len(data["loans"]) == 3
    assert data["loans"][0]["id"] == l3.id
    assert data["loans"][1]["id"] == l2.id
    assert data["loans"][2]["id"] == l1.id

    # Verify payments: 2 present, ordered newest first (p2, p1)
    assert len(data["payments"]) == 2
    assert data["payments"][0]["id"] == p2.id
    assert data["payments"][1]["id"] == p1.id

    # Verify totals
    assert data["total_fees_charged"] == 3000
    assert data["total_payments_recorded"] == 1500
    assert data["current_outstanding_balance"] == 1500


def test_get_member_statement_missing_member_returns_404(client: TestClient):
    """GET /members/999999/statement returns 404 NOT_FOUND."""
    res = client.get("/members/999999/statement")
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_get_member_statement_empty_history(client: TestClient):
    """Member with no loans or payments returns empty arrays and zero totals."""
    member_data = create_test_member(client)
    res = client.get(f"/members/{member_data['id']}/statement")
    assert res.status_code == 200
    data = res.json()
    assert data["loans"] == []
    assert data["payments"] == []
    assert data["total_fees_charged"] == 0
    assert data["total_payments_recorded"] == 0
    assert data["current_outstanding_balance"] == 0


def test_get_member_statement_is_read_only(client: TestClient, session: Session):
    """GET statement does not mutate balances, loans, or items."""
    member_data = create_test_member(client)
    member_id = member_data["id"]

    db_m = session.get(Member, member_id)
    db_m.running_fee_balance = 2500
    session.commit()

    # Call statement multiple times
    client.get(f"/members/{member_id}/statement")
    client.get(f"/members/{member_id}/statement")

    # Verify balance untouched
    session.expire_all()
    fresh_m = session.get(Member, member_id)
    assert fresh_m.running_fee_balance == 2500


def test_get_member_statement_api_alias_parity(client: TestClient):
    """GET /api/members/{id}/statement works identically to /members/{id}/statement."""
    member_data = create_test_member(client)
    res = client.get(f"/api/members/{member_data['id']}/statement")
    assert res.status_code == 200
    assert res.json()["member_id"] == member_data["id"]
