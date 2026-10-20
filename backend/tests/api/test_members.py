"""Focused API tests for Member endpoints."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
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


def test_list_members_empty(client: TestClient):
    """GET /members returns an empty list when no members exist."""
    response = client.get("/members")
    assert response.status_code == 200
    assert response.json() == []
    assert "X-Request-ID" in response.headers


def test_create_member_success(client: TestClient):
    """POST /members creates an active member with zero balance and returns 201."""
    payload = {"name": "Alice Smith", "phone": "+91-98765-00001"}
    response = client.post("/members", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Alice Smith"
    assert data["phone"] == "+91-98765-00001"
    assert data["status"] == "ACTIVE"
    assert data["running_fee_balance"] == 0
    assert "join_date" in data


def test_create_member_validation_errors(client: TestClient):
    """POST /members rejects invalid or empty fields with 422."""
    # Empty name
    res1 = client.post("/members", json={"name": "", "phone": "+91-11111-11111"})
    assert res1.status_code == 422
    assert res1.json()["code"] == "VALIDATION_ERROR"

    # Missing phone
    res2 = client.post("/members", json={"name": "Alice"})
    assert res2.status_code == 422

    # Empty payload
    res3 = client.post("/members", json={})
    assert res3.status_code == 422


def test_create_member_rejects_client_assigned_managed_fields(client: TestClient):
    """POST /members rejects attempts to set server-managed fields."""
    # Attempt to set status
    res1 = client.post(
        "/members",
        json={"name": "Bob", "phone": "+91-2", "status": "SUSPENDED"},
    )
    assert res1.status_code == 422
    assert "extra_forbidden" in str(res1.json()) or "status" in res1.json()["detail"]

    # Attempt to set running_fee_balance
    res2 = client.post(
        "/members",
        json={"name": "Bob", "phone": "+91-2", "running_fee_balance": 5000},
    )
    assert res2.status_code == 422

    # Attempt to assign an ID
    res3 = client.post(
        "/members",
        json={"name": "Bob", "phone": "+91-2", "id": 999},
    )
    assert res3.status_code == 422


def test_get_member_by_id_success(client: TestClient, session: Session):
    """GET /members/{id} returns member details."""
    created = client.post("/members", json={"name": "Charlie", "phone": "+91-98765-00003"}).json()

    response = client.get(f"/members/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["name"] == "Charlie"


def test_get_member_not_found(client: TestClient):
    """GET /members/{id} returns 404 for a nonexistent member."""
    response = client.get("/members/99999")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "NOT_FOUND"
    assert "99999" in data["detail"]


def test_update_member_profile_success(client: TestClient):
    """PATCH /members/{id} updates permitted profile fields."""
    created = client.post("/members", json={"name": "David", "phone": "+91-98765-00004"}).json()

    update_res = client.patch(
        f"/members/{created['id']}",
        json={"name": "David Bowie", "phone": "+91-98765-99999"},
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["name"] == "David Bowie"
    assert data["phone"] == "+91-98765-99999"
    assert data["status"] == "ACTIVE"
    assert data["running_fee_balance"] == 0


def test_update_member_profile_rejects_managed_fields(client: TestClient):
    """PATCH /members/{id} rejects attempts to overwrite status or balance."""
    created = client.post("/members", json={"name": "Eva", "phone": "+91-98765-00005"}).json()

    res1 = client.patch(
        f"/members/{created['id']}",
        json={"status": "SUSPENDED"},
    )
    assert res1.status_code == 422

    res2 = client.patch(
        f"/members/{created['id']}",
        json={"running_fee_balance": 1000},
    )
    assert res2.status_code == 422


def test_update_member_not_found(client: TestClient):
    """PATCH /members/{id} returns 404 for nonexistent member."""
    response = client.patch("/members/99999", json={"name": "Nobody"})
    assert response.status_code == 404


def test_suspend_and_reinstate_member(client: TestClient):
    """POST /members/{id}/suspend and /reinstate properly transition member status."""
    created = client.post("/members", json={"name": "Frank", "phone": "+91-98765-00006"}).json()
    mid = created["id"]
    assert created["status"] == "ACTIVE"

    # Suspend
    sus_res = client.post(f"/members/{mid}/suspend")
    assert sus_res.status_code == 200
    assert sus_res.json()["status"] == "SUSPENDED"

    # Reinstate
    rein_res = client.post(f"/members/{mid}/reinstate")
    assert rein_res.status_code == 200
    assert rein_res.json()["status"] == "ACTIVE"

    # Alias /reactivate also works
    client.post(f"/members/{mid}/suspend")
    react_res = client.post(f"/members/{mid}/reactivate")
    assert react_res.status_code == 200
    assert react_res.json()["status"] == "ACTIVE"


def test_suspend_member_not_found(client: TestClient):
    """POST /members/{id}/suspend returns 404 for nonexistent member."""
    response = client.post("/members/99999/suspend")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_list_members_filtering_and_api_prefix(client: TestClient):
    """GET /members supports filtering by status, and /api/members alias works identically."""
    m1 = client.post("/members", json={"name": "Active 1", "phone": "+91-11"}).json()
    m2 = client.post("/members", json={"name": "Active 2", "phone": "+91-22"}).json()
    client.post(f"/members/{m2['id']}/suspend")

    # Filter by ACTIVE
    res_active = client.get("/members?status=ACTIVE")
    assert res_active.status_code == 200
    active_ids = [m["id"] for m in res_active.json()]
    assert m1["id"] in active_ids
    assert m2["id"] not in active_ids

    # Filter by SUSPENDED
    res_suspended = client.get("/members?status=SUSPENDED")
    assert res_suspended.status_code == 200
    suspended_ids = [m["id"] for m in res_suspended.json()]
    assert m2["id"] in suspended_ids
    assert m1["id"] not in suspended_ids

    # Test /api/members prefix alias
    res_alias = client.get(f"/api/members/{m1['id']}")
    assert res_alias.status_code == 200
    assert res_alias.json()["id"] == m1["id"]


def test_create_member_whitespace_only_rejected(client: TestClient):
    """POST /members rejects whitespace-only fields with HTTP 422, not 500."""
    res1 = client.post("/members", json={"name": "   ", "phone": "+91-98765-00001"})
    assert res1.status_code == 422
    assert res1.json()["code"] == "VALIDATION_ERROR"
    assert "name" in res1.json()["detail"]

    res2 = client.post("/members", json={"name": "Alice", "phone": "   "})
    assert res2.status_code == 422
    assert res2.json()["code"] == "VALIDATION_ERROR"
    assert "phone" in res2.json()["detail"]


def test_create_member_normalizes_whitespace(client: TestClient):
    """POST /members normalizes leading and trailing whitespace."""
    payload = {"name": "  Grace Hopper  ", "phone": "  +91-98765-11111  "}
    response = client.post("/members", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Grace Hopper"
    assert data["phone"] == "+91-98765-11111"


def test_update_member_whitespace_only_rejected(client: TestClient):
    """PATCH /members/{id} rejects whitespace-only fields with HTTP 422, not 500."""
    created = client.post("/members", json={"name": "Henry", "phone": "+91-98765-00007"}).json()
    mid = created["id"]

    res1 = client.patch(f"/members/{mid}", json={"name": "   "})
    assert res1.status_code == 422
    assert res1.json()["code"] == "VALIDATION_ERROR"
    assert "name" in res1.json()["detail"]

    res2 = client.patch(f"/members/{mid}", json={"phone": "   "})
    assert res2.status_code == 422
    assert res2.json()["code"] == "VALIDATION_ERROR"
    assert "phone" in res2.json()["detail"]


def test_update_member_normalizes_whitespace(client: TestClient):
    """PATCH /members/{id} normalizes leading and trailing whitespace."""
    created = client.post("/members", json={"name": "Iris", "phone": "+91-98765-00008"}).json()
    mid = created["id"]

    res = client.patch(
        f"/members/{mid}",
        json={"name": "  Iris Murdoch  ", "phone": "  +91-98765-88888  "},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Iris Murdoch"
    assert res.json()["phone"] == "+91-98765-88888"


def test_delete_member_success(client: TestClient):
    """DELETE /members/{id} deletes a member with no history and returns 204."""
    created = client.post("/members", json={"name": "Delete Me", "phone": "+91-99999-00001"}).json()
    mid = created["id"]

    res = client.delete(f"/members/{mid}")
    assert res.status_code == 204
    assert res.text == ""

    # Verify member is gone
    get_res = client.get(f"/members/{mid}")
    assert get_res.status_code == 404
    assert get_res.json()["code"] == "NOT_FOUND"


def test_delete_member_nonexistent(client: TestClient):
    """DELETE /members/{id} returns 404 when member does not exist."""
    res = client.delete("/members/999999")
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_delete_member_with_loan_conflict(client: TestClient):
    """DELETE /members/{id} returns 409 when member has an associated loan."""
    m = client.post("/members", json={"name": "Borrower", "phone": "+91-99999-00002"}).json()
    i = client.post(
        "/items",
        json={"name": "Drill", "category": "Tools", "replacement_value": 50000},
    ).json()

    # Reserve loan
    loan_res = client.post("/loans/reserve", json={"member_id": m["id"], "item_id": i["id"]})
    assert loan_res.status_code == 201

    # Attempt delete
    res = client.delete(f"/members/{m['id']}")
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_DELETE_ASSOCIATED_RECORDS"
    assert "associated loan" in res.json()["detail"].lower()


def test_delete_member_with_payment_conflict(client: TestClient, session: Session):
    """DELETE /members/{id} returns 409 when member has a payment record."""
    m = client.post("/members", json={"name": "Payer", "phone": "+91-99999-00003"}).json()
    mid = m["id"]

    # Record a payment directly via session
    payment = Payment(member_id=mid, amount=1000, paid_at=datetime.now(UTC), note="Initial fee")
    session.add(payment)
    session.commit()

    res = client.delete(f"/members/{mid}")
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_DELETE_ASSOCIATED_RECORDS"
    assert "payment" in res.json()["detail"].lower()


def test_delete_member_with_outstanding_balance_conflict(client: TestClient, session: Session):
    """DELETE /members/{id} returns 409 when member has an outstanding fee balance."""
    m = client.post("/members", json={"name": "Debtor", "phone": "+91-99999-00004"}).json()
    mid = m["id"]

    db_m = session.get(Member, mid)
    assert db_m is not None
    db_m.running_fee_balance = 5000
    session.commit()

    res = client.delete(f"/members/{mid}")
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_DELETE_ASSOCIATED_RECORDS"
    assert "outstanding balance" in res.json()["detail"].lower()


def test_delete_member_api_prefix_alias(client: TestClient):
    """DELETE /api/members/{id} works identically via alias route."""
    m = client.post("/members", json={"name": "Alias Test", "phone": "+91-99999-00005"}).json()
    mid = m["id"]

    res = client.delete(f"/api/members/{mid}")
    assert res.status_code == 204

    get_res = client.get(f"/api/members/{mid}")
    assert get_res.status_code == 404
