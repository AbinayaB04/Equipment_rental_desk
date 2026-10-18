"""Focused API tests for Item endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app


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
