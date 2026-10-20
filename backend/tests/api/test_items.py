"""Focused API tests for Item endpoints."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db
from app.main import create_app
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus


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


def test_list_items_empty(client: TestClient):
    """GET /items returns an empty list when no items exist."""
    response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == []
    assert "X-Request-ID" in response.headers


def test_create_item_success(client: TestClient):
    """POST /items creates an available item and returns 201."""
    payload = {
        "name": "Circular Saw 7-1/4 inch",
        "category": "Saws",
        "replacement_value": 550000,
        "condition_note": "Blade guard checked",
    }
    response = client.post("/items", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Circular Saw 7-1/4 inch"
    assert data["category"] == "Saws"
    assert data["replacement_value"] == 550000
    assert data["condition_note"] == "Blade guard checked"
    assert data["status"] == "AVAILABLE"


def test_create_item_validation_errors(client: TestClient):
    """POST /items rejects invalid or negative replacement values with 422."""
    # Negative replacement value
    res1 = client.post(
        "/items",
        json={"name": "Drill", "category": "Drills", "replacement_value": -500},
    )
    assert res1.status_code == 422
    assert res1.json()["code"] == "VALIDATION_ERROR"

    # Zero replacement value
    res2 = client.post(
        "/items",
        json={"name": "Drill", "category": "Drills", "replacement_value": 0},
    )
    assert res2.status_code == 422

    # Blank name
    res3 = client.post(
        "/items",
        json={"name": "", "category": "Drills", "replacement_value": 1000},
    )
    assert res3.status_code == 422

    # Missing category
    res4 = client.post(
        "/items",
        json={"name": "Drill", "replacement_value": 1000},
    )
    assert res4.status_code == 422


def test_create_item_rejects_lifecycle_status_bypass(client: TestClient):
    """POST /items rejects attempts to assign non-available or managed status."""
    res1 = client.post(
        "/items",
        json={
            "name": "Drill",
            "category": "Drills",
            "replacement_value": 1000,
            "status": "CHECKED_OUT",
        },
    )
    assert res1.status_code == 422
    assert "extra_forbidden" in str(res1.json()) or "status" in res1.json()["detail"]

    res2 = client.post(
        "/items",
        json={
            "name": "Drill",
            "category": "Drills",
            "replacement_value": 1000,
            "status": "RESERVED",
        },
    )
    assert res2.status_code == 422

    res3 = client.post(
        "/items",
        json={
            "name": "Drill",
            "category": "Drills",
            "replacement_value": 1000,
            "id": 999,
        },
    )
    assert res3.status_code == 422


def test_get_item_by_id_success(client: TestClient):
    """GET /items/{id} returns item details."""
    created = client.post(
        "/items",
        json={"name": "Hammer Drill", "category": "Drills", "replacement_value": 800000},
    ).json()

    response = client.get(f"/items/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["name"] == "Hammer Drill"
    assert response.json()["status"] == "AVAILABLE"


def test_get_item_not_found(client: TestClient):
    """GET /items/{id} returns 404 with structured error response for nonexistent item."""
    response = client.get("/items/99999")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "NOT_FOUND"
    assert "99999" in data["detail"]


def test_update_item_metadata_success(client: TestClient):
    """PATCH /items/{id} updates permitted metadata."""
    created = client.post(
        "/items",
        json={"name": "Old Saw", "category": "Saws", "replacement_value": 40000},
    ).json()

    update_res = client.patch(
        f"/items/{created['id']}",
        json={
            "name": "Upgraded Saw",
            "category": "Precision Saws",
            "replacement_value": 45000,
            "condition_note": "New carbide blade",
        },
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["name"] == "Upgraded Saw"
    assert data["category"] == "Precision Saws"
    assert data["replacement_value"] == 45000
    assert data["condition_note"] == "New carbide blade"
    assert data["status"] == "AVAILABLE"


def test_update_item_rejects_status_change(client: TestClient):
    """PATCH /items/{id} rejects attempts to bypass maintenance/loan lifecycle."""
    created = client.post(
        "/items",
        json={"name": "Jigsaw", "category": "Saws", "replacement_value": 30000},
    ).json()

    res1 = client.patch(
        f"/items/{created['id']}",
        json={"status": "CHECKED_OUT"},
    )
    assert res1.status_code == 422

    res2 = client.patch(
        f"/items/{created['id']}",
        json={"status": "UNDER_MAINTENANCE"},
    )
    assert res2.status_code == 422


def test_update_item_not_found(client: TestClient):
    """PATCH /items/{id} returns 404 for nonexistent item."""
    response = client.patch("/items/99999", json={"name": "Nothing"})
    assert response.status_code == 404


def test_item_maintenance_lifecycle(client: TestClient):
    """POST /items/{id}/maintenance and /restore-maintenance transition status correctly."""
    created = client.post(
        "/items",
        json={"name": "Router", "category": "Woodworking", "replacement_value": 35000},
    ).json()
    iid = created["id"]
    assert created["status"] == "AVAILABLE"

    # Place in maintenance
    maint_res = client.post(f"/items/{iid}/maintenance")
    assert maint_res.status_code == 200
    assert maint_res.json()["status"] == "UNDER_MAINTENANCE"

    # Restore from maintenance
    rest_res = client.post(f"/items/{iid}/restore-maintenance")
    assert rest_res.status_code == 200
    assert rest_res.json()["status"] == "AVAILABLE"

    # Restoring an already AVAILABLE item raises InvalidItemStateError -> 409 Conflict
    conflict_res = client.post(f"/items/{iid}/restore-maintenance")
    assert conflict_res.status_code == 409
    assert conflict_res.json()["code"] == "INVALID_ITEM_STATE"

    # Alias /restore also works
    client.post(f"/items/{iid}/maintenance")
    alias_res = client.post(f"/items/{iid}/restore")
    assert alias_res.status_code == 200
    assert alias_res.json()["status"] == "AVAILABLE"


def test_item_maintenance_not_found(client: TestClient):
    """POST /items/{id}/maintenance returns 404 for nonexistent item."""
    response = client.post("/items/99999/maintenance")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_list_items_filtering_and_api_prefix(client: TestClient):
    """GET /items supports category and status filters, and /api/items alias works."""
    i1 = client.post(
        "/items",
        json={"name": "Drill 1", "category": "Drills", "replacement_value": 20000},
    ).json()
    i2 = client.post(
        "/items",
        json={"name": "Saw 1", "category": "Saws", "replacement_value": 30000},
    ).json()
    client.post(f"/items/{i2['id']}/maintenance")

    # Filter by category
    res_drills = client.get("/items?category=Drills")
    assert res_drills.status_code == 200
    drill_ids = [item["id"] for item in res_drills.json()]
    assert i1["id"] in drill_ids
    assert i2["id"] not in drill_ids

    # Filter by status
    res_maint = client.get("/items?status=UNDER_MAINTENANCE")
    assert res_maint.status_code == 200
    maint_ids = [item["id"] for item in res_maint.json()]
    assert i2["id"] in maint_ids
    assert i1["id"] not in maint_ids

    # Test /api/items prefix alias
    res_alias = client.get(f"/api/items/{i1['id']}")
    assert res_alias.status_code == 200
    assert res_alias.json()["id"] == i1["id"]


def test_create_item_whitespace_only_rejected(client: TestClient):
    """POST /items rejects whitespace-only fields with HTTP 422, not 500."""
    res1 = client.post(
        "/items",
        json={"name": "   ", "category": "Saws", "replacement_value": 1000},
    )
    assert res1.status_code == 422
    assert res1.json()["code"] == "VALIDATION_ERROR"
    assert "name" in res1.json()["detail"]

    res2 = client.post(
        "/items",
        json={"name": "Saw", "category": "   ", "replacement_value": 1000},
    )
    assert res2.status_code == 422
    assert res2.json()["code"] == "VALIDATION_ERROR"
    assert "category" in res2.json()["detail"]


def test_create_item_normalizes_whitespace_and_optional_notes(client: TestClient):
    """POST /items normalizes whitespace and converts whitespace-only notes to None."""
    payload1 = {
        "name": "  Angle Grinder  ",
        "category": "  Grinders  ",
        "replacement_value": 45000,
        "condition_note": "  Good condition  ",
    }
    res1 = client.post("/items", json=payload1)
    assert res1.status_code == 201
    assert res1.json()["name"] == "Angle Grinder"
    assert res1.json()["category"] == "Grinders"
    assert res1.json()["condition_note"] == "Good condition"

    # Whitespace-only optional condition_note normalizes to None without error
    payload2 = {
        "name": "Orbital Sander",
        "category": "Sanders",
        "replacement_value": 30000,
        "condition_note": "   ",
    }
    res2 = client.post("/items", json=payload2)
    assert res2.status_code == 201
    assert res2.json()["condition_note"] is None


def test_update_item_whitespace_only_rejected(client: TestClient):
    """PATCH /items/{id} rejects whitespace-only fields with HTTP 422, not 500."""
    created = client.post(
        "/items",
        json={"name": "Planer", "category": "Woodworking", "replacement_value": 25000},
    ).json()
    iid = created["id"]

    res1 = client.patch(f"/items/{iid}", json={"name": "   "})
    assert res1.status_code == 422
    assert res1.json()["code"] == "VALIDATION_ERROR"
    assert "name" in res1.json()["detail"]

    res2 = client.patch(f"/items/{iid}", json={"category": "   "})
    assert res2.status_code == 422
    assert res2.json()["code"] == "VALIDATION_ERROR"
    assert "category" in res2.json()["detail"]


def test_update_item_normalizes_whitespace_and_optional_notes(client: TestClient):
    """PATCH /items/{id} normalizes whitespace and converts whitespace-only notes to None."""
    created = client.post(
        "/items",
        json={
            "name": "Heat Gun",
            "category": "Electric",
            "replacement_value": 15000,
            "condition_note": "Initial note",
        },
    ).json()
    iid = created["id"]

    # Normalization of valid text
    res1 = client.patch(
        f"/items/{iid}",
        json={"name": "  Industrial Heat Gun  ", "category": "  Heating  "},
    )
    assert res1.status_code == 200
    assert res1.json()["name"] == "Industrial Heat Gun"
    assert res1.json()["category"] == "Heating"

    # Whitespace-only condition note clears it to None
    res2 = client.patch(f"/items/{iid}", json={"condition_note": "   "})
    assert res2.status_code == 200
    assert res2.json()["condition_note"] is None


def test_get_item_expired_reservation_presents_as_available(client: TestClient, session: Session):
    """GET /items/{id} presents an expired reservation (> 48h) dynamically as AVAILABLE
    without mutating the database entity.
    """
    # 1. Create item and member
    item_res = client.post(
        "/items",
        json={"name": "Heavy Duty Router", "category": "Routers", "replacement_value": 45000},
    ).json()
    item_id = item_res["id"]

    member_res = client.post(
        "/members",
        json={"name": "Priya Sharma", "phone": "+91-98765-11111"},
    ).json()
    member_id = member_res["id"]

    # 2. Reserve item
    res = client.post("/loans/reserve", json={"member_id": member_id, "item_id": item_id})
    assert res.status_code == 201

    # Stored status in DB is RESERVED
    loan = (
        session.query(Loan)
        .filter(Loan.item_id == item_id, Loan.status == LoanStatus.RESERVED)
        .first()
    )
    assert loan is not None
    # Simulate reservation that is 49 hours old (> 48h expiry threshold)
    loan.reserved_at = datetime.now(UTC) - timedelta(hours=49)
    session.commit()

    # 3. GET /items/{id} returns AVAILABLE
    resp = client.get(f"/items/{item_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == item_id
    assert data["status"] == "AVAILABLE"

    # 4. Read purity: DB persisted status remains RESERVED (no mutation on read)
    session.expire_all()
    persisted_item = session.get(Item, item_id)
    assert persisted_item is not None
    assert persisted_item.status == ItemStatus.RESERVED


def test_list_items_status_available_includes_expired_reservations(
    client: TestClient, session: Session
):
    """GET /items?status=AVAILABLE includes items with expired reservations,
    while status=RESERVED excludes them.
    """
    # Create member
    member = client.post(
        "/members", json={"name": "Anand Kumar", "phone": "+91-98765-22222"}
    ).json()

    # 1. Stored AVAILABLE item
    i_avail = client.post(
        "/items",
        json={"name": "Bench Grinder", "category": "Grinders", "replacement_value": 30000},
    ).json()

    # 2. Item with expired reservation (> 48h)
    i_expired = client.post(
        "/items",
        json={"name": "Angle Grinder", "category": "Grinders", "replacement_value": 25000},
    ).json()
    client.post("/loans/reserve", json={"member_id": member["id"], "item_id": i_expired["id"]})
    loan_exp = (
        session.query(Loan)
        .filter(Loan.item_id == i_expired["id"], Loan.status == LoanStatus.RESERVED)
        .first()
    )
    assert loan_exp is not None
    loan_exp.reserved_at = datetime.now(UTC) - timedelta(hours=50)

    # 3. Item with active reservation (< 48h)
    i_active = client.post(
        "/items",
        json={"name": "Die Grinder", "category": "Grinders", "replacement_value": 20000},
    ).json()
    client.post("/loans/reserve", json={"member_id": member["id"], "item_id": i_active["id"]})

    # 4. Item under maintenance
    i_maint = client.post(
        "/items",
        json={"name": "Surface Grinder", "category": "Grinders", "replacement_value": 80000},
    ).json()
    client.post(f"/items/{i_maint['id']}/maintenance")

    session.commit()

    # Query status=AVAILABLE
    res_avail = client.get("/items?status=AVAILABLE")
    assert res_avail.status_code == 200
    avail_ids = [item["id"] for item in res_avail.json()]
    assert i_avail["id"] in avail_ids
    assert i_expired["id"] in avail_ids
    assert i_active["id"] not in avail_ids
    assert i_maint["id"] not in avail_ids

    # Query status=AVAILABLE with category filter
    res_grinders_avail = client.get("/items?category=Grinders&status=AVAILABLE")
    assert res_grinders_avail.status_code == 200
    grinder_avail_ids = [item["id"] for item in res_grinders_avail.json()]
    assert i_avail["id"] in grinder_avail_ids
    assert i_expired["id"] in grinder_avail_ids

    # Verify presented status is AVAILABLE for all items in AVAILABLE listing
    for item in res_avail.json():
        if item["id"] == i_expired["id"]:
            assert item["status"] == "AVAILABLE"

    # Query status=RESERVED
    res_reserved = client.get("/items?status=RESERVED")
    assert res_reserved.status_code == 200
    reserved_ids = [item["id"] for item in res_reserved.json()]
    assert i_active["id"] in reserved_ids
    assert i_expired["id"] not in reserved_ids
    assert i_avail["id"] not in reserved_ids
    assert i_maint["id"] not in reserved_ids

    # Query unauthenticated GET /items (all items)
    res_all = client.get("/items")
    assert res_all.status_code == 200
    all_map = {item["id"]: item for item in res_all.json()}
    assert all_map[i_expired["id"]]["status"] == "AVAILABLE"
    assert all_map[i_active["id"]]["status"] == "RESERVED"


def test_get_item_active_reservation_remains_reserved(client: TestClient, session: Session):
    """GET /items/{id} presents an unexpired reservation (< 48h) as RESERVED."""
    member = client.post(
        "/members", json={"name": "Rahul Verma", "phone": "+91-98765-33333"}
    ).json()
    item = client.post(
        "/items",
        json={"name": "Tile Saw 10-inch", "category": "Saws", "replacement_value": 70000},
    ).json()

    client.post("/loans/reserve", json={"member_id": member["id"], "item_id": item["id"]})

    # Set reservation time to 47 hours ago (1 hour before expiry)
    loan = (
        session.query(Loan)
        .filter(Loan.item_id == item["id"], Loan.status == LoanStatus.RESERVED)
        .first()
    )
    assert loan is not None
    loan.reserved_at = datetime.now(UTC) - timedelta(hours=47)
    session.commit()

    # GET /items/{id} must show RESERVED
    res_single = client.get(f"/items/{item['id']}")
    assert res_single.status_code == 200
    assert res_single.json()["status"] == "RESERVED"

    # GET /items?status=RESERVED must include it
    res_reserved = client.get("/items?status=RESERVED")
    assert res_reserved.status_code == 200
    assert item["id"] in [i["id"] for i in res_reserved.json()]

    # GET /items?status=AVAILABLE must NOT include it
    res_avail = client.get("/items?status=AVAILABLE")
    assert res_avail.status_code == 200
    assert item["id"] not in [i["id"] for i in res_avail.json()]


def test_item_dynamic_expiry_with_reviewer_test_clock(client: TestClient):
    """GET /items and GET /items/{id} dynamically update status according to X-Test-Clock."""
    # Enable test clock on client app
    client.app.state.settings = Settings(
        app_env="development",
        database_url="",
        cors_origins=(),
        log_level="INFO",
        allow_test_clock=True,
    )

    member = client.post("/members", json={"name": "Deepa Nair", "phone": "+91-98765-44444"}).json()
    item = client.post(
        "/items",
        json={"name": "Rotary Laser Level", "category": "Levels", "replacement_value": 90000},
    ).json()
    item_id = item["id"]

    # Base reservation timestamp: 2026-10-25T10:00:00Z
    t0 = datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC)
    t0_str = t0.isoformat()

    reserve_res = client.post(
        "/loans/reserve",
        json={"member_id": member["id"], "item_id": item_id},
        headers={"X-Test-Clock": t0_str},
    )
    assert reserve_res.status_code == 201

    # 1. At t0 + 2 hours: reservation is active (< 48h)
    t_2h = (t0 + timedelta(hours=2)).isoformat()
    res_2h = client.get(f"/items/{item_id}", headers={"X-Test-Clock": t_2h})
    assert res_2h.status_code == 200
    assert res_2h.json()["status"] == "RESERVED"

    res_list_res_2h = client.get("/items?status=RESERVED", headers={"X-Test-Clock": t_2h})
    assert item_id in [i["id"] for i in res_list_res_2h.json()]

    res_list_avail_2h = client.get("/items?status=AVAILABLE", headers={"X-Test-Clock": t_2h})
    assert item_id not in [i["id"] for i in res_list_avail_2h.json()]

    # 2. At t0 + 47 hours 59 minutes: still valid (< 48h boundary)
    t_boundary_valid = (t0 + timedelta(hours=47, minutes=59)).isoformat()
    res_valid = client.get(f"/items/{item_id}", headers={"X-Test-Clock": t_boundary_valid})
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "RESERVED"

    # 3. At exactly t0 + 48 hours: expired (Rule 2 boundary)
    t_exact_48h = (t0 + timedelta(hours=48)).isoformat()
    res_exact = client.get(f"/items/{item_id}", headers={"X-Test-Clock": t_exact_48h})
    assert res_exact.status_code == 200
    assert res_exact.json()["status"] == "AVAILABLE"

    res_list_avail_exact = client.get(
        "/items?status=AVAILABLE", headers={"X-Test-Clock": t_exact_48h}
    )
    assert item_id in [i["id"] for i in res_list_avail_exact.json()]

    res_list_res_exact = client.get("/items?status=RESERVED", headers={"X-Test-Clock": t_exact_48h})
    assert item_id not in [i["id"] for i in res_list_res_exact.json()]

    # 4. At t0 + 72 hours: expired
    t_72h = (t0 + timedelta(hours=72)).isoformat()
    res_72h = client.get(f"/items/{item_id}", headers={"X-Test-Clock": t_72h})
    assert res_72h.status_code == 200
    assert res_72h.json()["status"] == "AVAILABLE"

    res_all_72h = client.get("/items", headers={"X-Test-Clock": t_72h})
    assert res_all_72h.status_code == 200
    items_72h = {i["id"]: i for i in res_all_72h.json()}
    assert items_72h[item_id]["status"] == "AVAILABLE"


def test_search_items_name_partial_and_case_insensitive(client: TestClient):
    """GET /items?q= matches item names partially and case-insensitively."""
    i1 = client.post(
        "/items",
        json={"name": "DeWalt Cordless Drill", "category": "Drills", "replacement_value": 45000},
    ).json()
    i2 = client.post(
        "/items",
        json={"name": "Bosch Hammer DRILL", "category": "Drills", "replacement_value": 60000},
    ).json()
    i3 = client.post(
        "/items",
        json={"name": "Makita Jigsaw", "category": "Saws", "replacement_value": 35000},
    ).json()

    # Case-insensitive lowercase partial
    res_lower = client.get("/items?q=cordless")
    assert res_lower.status_code == 200
    ids_lower = [item["id"] for item in res_lower.json()]
    assert i1["id"] in ids_lower
    assert i2["id"] not in ids_lower
    assert i3["id"] not in ids_lower

    # Case-insensitive uppercase partial
    res_upper = client.get("/items?q=DRILL")
    assert res_upper.status_code == 200
    ids_upper = [item["id"] for item in res_upper.json()]
    assert i1["id"] in ids_upper
    assert i2["id"] in ids_upper
    assert i3["id"] not in ids_upper

    # Mixed-case partial substring
    res_mixed = client.get("/items?q=mER")
    assert res_mixed.status_code == 200
    ids_mixed = [item["id"] for item in res_mixed.json()]
    assert i2["id"] in ids_mixed
    assert i1["id"] not in ids_mixed


def test_search_items_category_match(client: TestClient):
    """GET /items?q= matches item category case-insensitively."""
    item = client.post(
        "/items",
        json={
            "name": "Laser Measure 100m",
            "category": "Measuring Tools",
            "replacement_value": 25000,
        },
    ).json()

    # Search term matching category only
    res = client.get("/items?q=measuring")
    assert res.status_code == 200
    ids = [i["id"] for i in res.json()]
    assert item["id"] in ids

    # Search term matching category in uppercase
    res_upper = client.get("/items?q=TOOLS")
    assert res_upper.status_code == 200
    assert item["id"] in [i["id"] for i in res_upper.json()]


def test_search_items_no_matches(client: TestClient):
    """GET /items?q= returns an empty list when no items match."""
    client.post(
        "/items",
        json={"name": "Heavy Crowbar", "category": "Demolition", "replacement_value": 15000},
    )

    res = client.get("/items?q=nonexistent_xyz_query_12345")
    assert res.status_code == 200
    assert res.json() == []


def test_search_items_missing_and_whitespace_only(client: TestClient):
    """GET /items with missing or whitespace-only q returns all items
    preserving listing behavior.
    """
    i1 = client.post(
        "/items",
        json={"name": "Item Alpha", "category": "General", "replacement_value": 10000},
    ).json()
    i2 = client.post(
        "/items",
        json={"name": "Item Beta", "category": "General", "replacement_value": 10000},
    ).json()

    # Missing q
    res_missing = client.get("/items")
    assert res_missing.status_code == 200
    missing_ids = [i["id"] for i in res_missing.json()]
    assert i1["id"] in missing_ids
    assert i2["id"] in missing_ids

    # Empty string q
    res_empty = client.get("/items?q=")
    assert res_empty.status_code == 200
    empty_ids = [i["id"] for i in res_empty.json()]
    assert i1["id"] in empty_ids
    assert i2["id"] in empty_ids

    # Whitespace-only q
    res_whitespace = client.get("/items?q=%20%20%20")
    assert res_whitespace.status_code == 200
    ws_ids = [i["id"] for i in res_whitespace.json()]
    assert i1["id"] in ws_ids
    assert i2["id"] in ws_ids


def test_search_items_combined_with_status_and_expired_reservations(
    client: TestClient, session: Session
):
    """GET /items with search combined with status filtering and dynamic reservation expiry."""
    member = client.post("/members", json={"name": "Siddharth", "phone": "+91-98765-55555"}).json()

    # 1. Available Router
    i_avail = client.post(
        "/items",
        json={"name": "Plunge Router Pro", "category": "Woodworking", "replacement_value": 50000},
    ).json()

    # 2. Expired Router (> 48h)
    i_expired = client.post(
        "/items",
        json={"name": "Compact Palm Router", "category": "Woodworking", "replacement_value": 35000},
    ).json()
    client.post("/loans/reserve", json={"member_id": member["id"], "item_id": i_expired["id"]})
    loan_exp = (
        session.query(Loan)
        .filter(Loan.item_id == i_expired["id"], Loan.status == LoanStatus.RESERVED)
        .first()
    )
    assert loan_exp is not None
    loan_exp.reserved_at = datetime.now(UTC) - timedelta(hours=50)

    # 3. Active Router (< 48h)
    i_active = client.post(
        "/items",
        json={"name": "Fixed Base Router", "category": "Woodworking", "replacement_value": 40000},
    ).json()
    client.post("/loans/reserve", json={"member_id": member["id"], "item_id": i_active["id"]})

    # 4. Under maintenance Router
    i_maint = client.post(
        "/items",
        json={"name": "CNC Wood Router", "category": "Woodworking", "replacement_value": 150000},
    ).json()
    client.post(f"/items/{i_maint['id']}/maintenance")

    # 5. Non-matching item
    i_other = client.post(
        "/items",
        json={"name": "Pipe Wrench", "category": "Plumbing", "replacement_value": 12000},
    ).json()

    session.commit()

    # Search for "router" + status=AVAILABLE
    res_avail = client.get("/items?q=router&status=AVAILABLE")
    assert res_avail.status_code == 200
    avail_ids = [item["id"] for item in res_avail.json()]
    assert i_avail["id"] in avail_ids
    assert i_expired["id"] in avail_ids
    assert i_active["id"] not in avail_ids
    assert i_maint["id"] not in avail_ids
    assert i_other["id"] not in avail_ids

    # Search for "router" + status=RESERVED
    res_res = client.get("/items?q=router&status=RESERVED")
    assert res_res.status_code == 200
    res_ids = [item["id"] for item in res_res.json()]
    assert i_active["id"] in res_ids
    assert i_expired["id"] not in res_ids
    assert i_avail["id"] not in res_ids


def test_search_items_pagination_and_category_filter(client: TestClient):
    """GET /items combines search with category filtering, limit, and offset pagination."""
    s1 = client.post(
        "/items",
        json={"name": "Random Orbital Sander", "category": "Sanders", "replacement_value": 20000},
    ).json()
    s2 = client.post(
        "/items",
        json={"name": "Belt Sander 3x21", "category": "Sanders", "replacement_value": 35000},
    ).json()
    s3 = client.post(
        "/items",
        json={"name": "Detail Finishing Sander", "category": "Sanders", "replacement_value": 15000},
    ).json()
    s4 = client.post(
        "/items",
        json={
            "name": "Floor Drum Sander",
            "category": "Heavy Equipment",
            "replacement_value": 120000,
        },
    ).json()

    # Combined search + category filter
    res_cat = client.get("/items?q=sander&category=Sanders")
    assert res_cat.status_code == 200
    cat_ids = [i["id"] for i in res_cat.json()]
    assert s1["id"] in cat_ids
    assert s2["id"] in cat_ids
    assert s3["id"] in cat_ids
    assert s4["id"] not in cat_ids

    # Combined search + pagination (limit and offset)
    res_p1 = client.get("/items?q=sander&category=Sanders&limit=2&offset=0")
    assert res_p1.status_code == 200
    p1_items = res_p1.json()
    assert len(p1_items) == 2
    assert p1_items[0]["id"] == s1["id"]
    assert p1_items[1]["id"] == s2["id"]

    res_p2 = client.get("/items?q=sander&category=Sanders&limit=2&offset=2")
    assert res_p2.status_code == 200
    p2_items = res_p2.json()
    assert len(p2_items) == 1
    assert p2_items[0]["id"] == s3["id"]


def test_delete_item_success_available(client: TestClient):
    """DELETE /items/{id} deletes an available item with no history and returns 204."""
    created = client.post(
        "/items",
        json={"name": "Disposable Item", "category": "Misc", "replacement_value": 10000},
    ).json()
    item_id = created["id"]

    res = client.delete(f"/items/{item_id}")
    assert res.status_code == 204
    assert res.text == ""

    # Verify item is gone
    get_res = client.get(f"/items/{item_id}")
    assert get_res.status_code == 404
    assert get_res.json()["code"] == "NOT_FOUND"


def test_delete_item_success_in_maintenance(client: TestClient):
    """DELETE /items/{id} deletes an item in maintenance with no loan history and returns 204."""
    created = client.post(
        "/items",
        json={"name": "Maintenance Item", "category": "Misc", "replacement_value": 15000},
    ).json()
    item_id = created["id"]

    maint_res = client.post(f"/items/{item_id}/maintenance")
    assert maint_res.status_code == 200
    assert maint_res.json()["status"] == "UNDER_MAINTENANCE"

    res = client.delete(f"/items/{item_id}")
    assert res.status_code == 204

    get_res = client.get(f"/items/{item_id}")
    assert get_res.status_code == 404


def test_delete_item_nonexistent(client: TestClient):
    """DELETE /items/{id} returns 404 when item does not exist."""
    res = client.delete("/items/999999")
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_delete_item_with_loan_conflict(client: TestClient):
    """DELETE /items/{id} returns 409 when item has an active reservation or loan."""
    m = client.post("/members", json={"name": "Item Borrower", "phone": "+91-99999-00006"}).json()
    i = client.post(
        "/items",
        json={"name": "Reserved Drill", "category": "Tools", "replacement_value": 45000},
    ).json()

    loan_res = client.post("/loans/reserve", json={"member_id": m["id"], "item_id": i["id"]})
    assert loan_res.status_code == 201

    res = client.delete(f"/items/{i['id']}")
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_DELETE_ASSOCIATED_RECORDS"
    assert "associated loan" in res.json()["detail"].lower()


def test_delete_item_with_historical_loan_conflict(client: TestClient):
    """DELETE /items/{id} returns 409 when item has returned/historical loan records."""
    m = client.post("/members", json={"name": "Past Borrower", "phone": "+91-99999-00007"}).json()
    i = client.post(
        "/items",
        json={"name": "Historical Sander", "category": "Tools", "replacement_value": 30000},
    ).json()

    loan = client.post("/loans/reserve", json={"member_id": m["id"], "item_id": i["id"]}).json()
    client.post(f"/loans/{loan['id']}/checkout")
    client.post(f"/loans/{loan['id']}/return")

    res = client.delete(f"/items/{i['id']}")
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_DELETE_ASSOCIATED_RECORDS"
    assert "associated loan" in res.json()["detail"].lower()


def test_delete_item_api_prefix_alias(client: TestClient):
    """DELETE /api/items/{id} works identically via alias route."""
    created = client.post(
        "/items",
        json={"name": "Alias Item", "category": "Misc", "replacement_value": 20000},
    ).json()
    item_id = created["id"]

    res = client.delete(f"/api/items/{item_id}")
    assert res.status_code == 204

    get_res = client.get(f"/api/items/{item_id}")
    assert get_res.status_code == 404
