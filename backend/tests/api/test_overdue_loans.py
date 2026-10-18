"""Focused API tests for the Overdue Loans endpoint (GET /loans/overdue)."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db
from app.main import create_app
from app.models.loan import Loan


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


def create_member(
    client: TestClient,
    name: str = "Borrower",
    phone: str = "+91-98765-00000",
) -> dict:
    """Helper to create a member."""
    res = client.post("/members", json={"name": name, "phone": phone})
    assert res.status_code == 201
    return res.json()


def create_item(client: TestClient, name: str = "Drill") -> dict:
    """Helper to create an item."""
    payload = {"name": name, "category": "Tools", "replacement_value": 50000}
    res = client.post("/items", json=payload)
    assert res.status_code == 201
    return res.json()


# ============================================================================
# Overdue Loans API Tests (GET /loans/overdue)
# ============================================================================


def test_overdue_checked_out_loan_included(client: TestClient, session: Session):
    """A checked-out loan whose due_at is before current time is included."""
    now = datetime.now(UTC)
    member = create_member(client)
    item = create_item(client)

    # Reserve and checkout
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 201
    loan_id = res.json()["id"]
    checkout_res = client.post(f"/loans/{loan_id}/checkout")
    assert checkout_res.status_code == 200

    # Backdate checkout and due_at (due 2 days ago)
    db_loan = session.get(Loan, loan_id)
    assert db_loan is not None
    db_loan.checked_out_at = now - timedelta(days=9)
    db_loan.due_at = now - timedelta(days=2)
    session.commit()

    overdue_res = client.get("/loans/overdue")
    assert overdue_res.status_code == 200
    loans = overdue_res.json()
    loan_ids = [loan["id"] for loan in loans]
    assert loan_id in loan_ids


def test_loan_due_exactly_at_current_time_boundary(client: TestClient, session: Session):
    """Assumption 17: at exact due_at, loan is NOT overdue; strictly after due_at it is overdue."""
    app = client.app
    app.state.settings = Settings(
        app_env="development",
        database_url="",
        cors_origins=(),
        log_level="INFO",
        allow_test_clock=True,
    )

    t_checkout = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    t_due = t_checkout + timedelta(days=7)  # 2026-10-08 10:00:00 UTC

    member = create_member(client)
    item = create_item(client)

    res = client.post(
        "/loans/reserve",
        json={"member_id": member["id"], "item_id": item["id"]},
        headers={"X-Test-Clock": t_checkout.isoformat()},
    )
    assert res.status_code == 201
    loan_id = res.json()["id"]
    checkout_res = client.post(
        f"/loans/{loan_id}/checkout",
        headers={"X-Test-Clock": t_checkout.isoformat()},
    )
    assert checkout_res.status_code == 200

    # 1 second before due -> NOT overdue
    r_before = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": (t_due - timedelta(seconds=1)).isoformat()},
    )
    assert r_before.status_code == 200
    assert loan_id not in [loan["id"] for loan in r_before.json()]

    # Exactly at due_at -> NOT overdue (Assumption 17)
    r_exact = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": t_due.isoformat()},
    )
    assert r_exact.status_code == 200
    assert loan_id not in [loan["id"] for loan in r_exact.json()]

    # 1 second after due_at -> OVERDUE
    r_after = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": (t_due + timedelta(seconds=1)).isoformat()},
    )
    assert r_after.status_code == 200
    assert loan_id in [loan["id"] for loan in r_after.json()]


def test_loan_not_yet_due_excluded(client: TestClient):
    """A freshly checked-out loan with due date 7 days in the future is excluded."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 201
    loan_id = res.json()["id"]
    checkout_res = client.post(f"/loans/{loan_id}/checkout")
    assert checkout_res.status_code == 200

    overdue_res = client.get("/loans/overdue")
    assert overdue_res.status_code == 200
    assert loan_id not in [loan["id"] for loan in overdue_res.json()]


def test_returned_loan_excluded(client: TestClient, session: Session):
    """A returned loan is excluded from overdue list even if returned_at was after due_at."""
    now = datetime.now(UTC)
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 201
    loan_id = res.json()["id"]
    checkout_res = client.post(f"/loans/{loan_id}/checkout")
    assert checkout_res.status_code == 200

    # Backdate to make it overdue
    db_loan = session.get(Loan, loan_id)
    assert db_loan is not None
    db_loan.checked_out_at = now - timedelta(days=10)
    db_loan.due_at = now - timedelta(days=3)
    session.commit()

    # Return the loan
    ret_res = client.post(f"/loans/{loan_id}/return")
    assert ret_res.status_code == 200

    overdue_res = client.get("/loans/overdue")
    assert loan_id not in [loan["id"] for loan in overdue_res.json()]


def test_reservation_not_checked_out_excluded(client: TestClient, session: Session):
    """An un-checked-out reservation (even if old) is excluded from overdue loans."""
    now = datetime.now(UTC)
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 201
    loan_id = res.json()["id"]

    # Backdate reservation by 30 days
    db_loan = session.get(Loan, loan_id)
    assert db_loan is not None
    db_loan.reserved_at = now - timedelta(days=30)
    session.commit()

    overdue_res = client.get("/loans/overdue")
    assert loan_id not in [loan["id"] for loan in overdue_res.json()]


def test_cancelled_loan_excluded(client: TestClient):
    """A cancelled reservation is excluded from overdue loans."""
    member = create_member(client)
    item = create_item(client)
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 201
    loan_id = res.json()["id"]
    cancel_res = client.post(f"/loans/{loan_id}/cancel")
    assert cancel_res.status_code == 200

    overdue_res = client.get("/loans/overdue")
    assert loan_id not in [loan["id"] for loan in overdue_res.json()]


def test_multiple_overdue_loans_ordered_by_due_date(client: TestClient, session: Session):
    """Multiple overdue loans are all returned and ordered oldest due_at first."""
    now = datetime.now(UTC)
    m1 = create_member(client, name="Borrower 1", phone="+91-98765-00001")
    m2 = create_member(client, name="Borrower 2", phone="+91-98765-00002")
    m3 = create_member(client, name="Borrower 3", phone="+91-98765-00003")
    i1 = create_item(client, name="Item 1")
    i2 = create_item(client, name="Item 2")
    i3 = create_item(client, name="Item 3")

    r1 = client.post("/loans/reserve", json={"member_id": m1["id"], "item_id": i1["id"]})
    assert r1.status_code == 201
    l1_id = r1.json()["id"]
    c1 = client.post(f"/loans/{l1_id}/checkout")
    assert c1.status_code == 200

    r2 = client.post("/loans/reserve", json={"member_id": m2["id"], "item_id": i2["id"]})
    assert r2.status_code == 201
    l2_id = r2.json()["id"]
    c2 = client.post(f"/loans/{l2_id}/checkout")
    assert c2.status_code == 200

    r3 = client.post("/loans/reserve", json={"member_id": m3["id"], "item_id": i3["id"]})
    assert r3.status_code == 201
    l3_id = r3.json()["id"]
    c3 = client.post(f"/loans/{l3_id}/checkout")
    assert c3.status_code == 200

    # Set due dates: l2 due 5 days ago, l1 due 3 days ago, l3 due 1 day ago
    # Ensure checked_out_at is prior to due_at to satisfy ck_loans_checked_out_timestamps
    d1 = session.get(Loan, l1_id)
    assert d1 is not None
    d1.checked_out_at = now - timedelta(days=10)
    d1.due_at = now - timedelta(days=3)
    d2 = session.get(Loan, l2_id)
    assert d2 is not None
    d2.checked_out_at = now - timedelta(days=12)
    d2.due_at = now - timedelta(days=5)
    d3 = session.get(Loan, l3_id)
    assert d3 is not None
    d3.checked_out_at = now - timedelta(days=8)
    d3.due_at = now - timedelta(days=1)
    session.commit()

    overdue_res = client.get("/loans/overdue")
    assert overdue_res.status_code == 200
    loans = overdue_res.json()
    returned_ids = [loan["id"] for loan in loans if loan["id"] in {l1_id, l2_id, l3_id}]
    # Oldest due_at first: l2 (-5 days), l1 (-3 days), l3 (-1 day)
    assert returned_ids == [l2_id, l1_id, l3_id]


def test_overdue_loans_respects_injected_test_clock(client: TestClient, session: Session):
    """The overdue loans endpoint respects the injected X-Test-Clock when allowed."""
    app = client.app
    app.state.settings = Settings(
        app_env="development",
        database_url="",
        cors_origins=(),
        log_level="INFO",
        allow_test_clock=True,
    )

    t_checkout = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    member = create_member(client, name="Clock Borrower", phone="+91-98765-55555")
    item = create_item(client, name="Clock Item")

    res = client.post(
        "/loans/reserve",
        json={"member_id": member["id"], "item_id": item["id"]},
        headers={"X-Test-Clock": t_checkout.isoformat()},
    )
    assert res.status_code == 201
    loan_id = res.json()["id"]
    c = client.post(
        f"/loans/{loan_id}/checkout",
        headers={"X-Test-Clock": t_checkout.isoformat()},
    )
    assert c.status_code == 200

    # Due at 2026-10-08 10:00:00 UTC
    # Query with test clock before due date -> not overdue
    r_past = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": "2026-10-05T10:00:00Z"},
    )
    assert loan_id not in [loan["id"] for loan in r_past.json()]

    # Query with test clock after due date -> overdue
    r_future = client.get(
        "/loans/overdue",
        headers={"X-Test-Clock": "2026-10-15T10:00:00Z"},
    )
    assert loan_id in [loan["id"] for loan in r_future.json()]


def test_overdue_loans_pagination(client: TestClient, session: Session):
    """Pagination query params limit and offset work on GET /loans/overdue."""
    now = datetime.now(UTC)

    loan_ids: list[int] = []
    for i in range(5):
        mem = create_member(client, name=f"Pagination Borrower {i}", phone=f"+91-98765-1000{i}")
        it = create_item(client, name=f"Pagination Item {i}")
        r = client.post("/loans/reserve", json={"member_id": mem["id"], "item_id": it["id"]})
        assert r.status_code == 201
        lid = r.json()["id"]
        c = client.post(f"/loans/{lid}/checkout")
        assert c.status_code == 200
        db_l = session.get(Loan, lid)
        assert db_l is not None
        db_l.checked_out_at = now - timedelta(days=20)
        db_l.due_at = now - timedelta(days=10 - i)  # Ordered 10, 9, 8, 7, 6 days ago
        session.commit()
        loan_ids.append(lid)

    # Page 1: limit 2, offset 0 -> first 2 loans
    p1 = client.get("/loans/overdue?limit=2&offset=0").json()
    assert len(p1) == 2
    assert [loan["id"] for loan in p1] == loan_ids[0:2]

    # Page 2: limit 2, offset 2 -> next 2 loans
    p2 = client.get("/loans/overdue?limit=2&offset=2").json()
    assert len(p2) == 2
    assert [loan["id"] for loan in p2] == loan_ids[2:4]

    # Page 3: limit 2, offset 4 -> 5th loan
    p3 = client.get("/loans/overdue?limit=2&offset=4").json()
    assert len(p3) == 1
    assert [loan["id"] for loan in p3] == [loan_ids[4]]


def test_overdue_loans_filters_by_member_and_item(client: TestClient, session: Session):
    """Filtering by member_id and item_id isolates specific overdue loans."""
    now = datetime.now(UTC)
    m1 = create_member(client, name="Filter Borrower 1", phone="+91-98765-20001")
    m2 = create_member(client, name="Filter Borrower 2", phone="+91-98765-20002")
    i1 = create_item(client, name="Filter Item 1")
    i2 = create_item(client, name="Filter Item 2")

    r1 = client.post("/loans/reserve", json={"member_id": m1["id"], "item_id": i1["id"]})
    l1_id = r1.json()["id"]
    client.post(f"/loans/{l1_id}/checkout")

    r2 = client.post("/loans/reserve", json={"member_id": m2["id"], "item_id": i2["id"]})
    l2_id = r2.json()["id"]
    client.post(f"/loans/{l2_id}/checkout")

    d1 = session.get(Loan, l1_id)
    assert d1 is not None
    d1.checked_out_at = now - timedelta(days=10)
    d1.due_at = now - timedelta(days=3)
    d2 = session.get(Loan, l2_id)
    assert d2 is not None
    d2.checked_out_at = now - timedelta(days=10)
    d2.due_at = now - timedelta(days=2)
    session.commit()

    # Filter by member_id
    res_m1 = client.get(f"/loans/overdue?member_id={m1['id']}")
    assert res_m1.status_code == 200
    ids_m1 = [loan["id"] for loan in res_m1.json()]
    assert l1_id in ids_m1
    assert l2_id not in ids_m1

    # Filter by item_id
    res_i2 = client.get(f"/loans/overdue?item_id={i2['id']}")
    assert res_i2.status_code == 200
    ids_i2 = [loan["id"] for loan in res_i2.json()]
    assert l2_id in ids_i2
    assert l1_id not in ids_i2


def test_overdue_loans_api_alias_parity(client: TestClient, session: Session):
    """GET /api/loans/overdue behaves identically to GET /loans/overdue."""
    now = datetime.now(UTC)
    member = create_member(client, name="Alias Borrower", phone="+91-98765-99999")
    item = create_item(client, name="Alias Item")
    res = client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})
    assert res.status_code == 201
    loan_id = res.json()["id"]
    checkout_res = client.post(f"/loans/{loan_id}/checkout")
    assert checkout_res.status_code == 200

    db_loan = session.get(Loan, loan_id)
    assert db_loan is not None
    db_loan.checked_out_at = now - timedelta(days=8)
    db_loan.due_at = now - timedelta(days=1)
    session.commit()

    alias_res = client.get("/api/loans/overdue")
    assert alias_res.status_code == 200
    assert loan_id in [loan["id"] for loan in alias_res.json()]
