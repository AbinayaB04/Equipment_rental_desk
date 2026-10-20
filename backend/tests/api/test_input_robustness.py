"""Robustness and malformed-input regression tests.

Guarantees that no edge-case value (integer overflows, NUL characters, control
characters, lone surrogates, hostile path/query parameters, or clock overflows)
can ever trigger an unhandled HTTP 500 or leak database/driver errors to clients.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

MAX_DB_INT = 2_147_483_647
OVERFLOW_INT_32 = 2_147_483_648
OVERFLOW_INT_64 = 2**63
OVERFLOW_INT_BIG = 10**30
OVERFLOW_OFFSET = 10**20


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient against real application and real database."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def assert_error_envelope(response, expected_status: int = 422) -> dict:
    """Assert status code and standard error envelope with zero leaked internals."""
    assert (
        response.status_code == expected_status
    ), f"Expected {expected_status}, got {response.status_code}: {response.text}"
    data = response.json()
    assert "error" in data, f"Missing 'error' in response: {data}"
    assert "detail" in data, f"Missing 'detail' in response: {data}"
    assert "code" in data, f"Missing 'code' in response: {data}"
    assert "request_id" in data, f"Missing 'request_id' in response: {data}"
    assert "SQL" not in response.text
    assert "psycopg" not in response.text
    assert "Traceback" not in response.text
    return data


# --- 1. Money Bounds ---


def test_money_bounds_items_create(client: TestClient):
    """POST /items replacement_value edge cases: 0, -1, MAX_DB_INT, overflow."""
    # 0 and -1 are rejected with 422
    for bad_val in (0, -1):
        r = client.post(
            "/items",
            json={"name": "Hammer", "category": "Tools", "replacement_value": bad_val},
        )
        assert_error_envelope(r, 422)

    # MAX_DB_INT (2147483647) is valid and succeeds with 201
    r_valid = client.post(
        "/items",
        json={"name": "Expensive Tool", "category": "Tools", "replacement_value": MAX_DB_INT},
    )
    assert r_valid.status_code == 201
    assert r_valid.json()["replacement_value"] == MAX_DB_INT

    # Out of range 32-bit and arbitrary precision integers are rejected with 422, never 500
    for overflow_val in (OVERFLOW_INT_32, OVERFLOW_INT_64, OVERFLOW_INT_BIG):
        r = client.post(
            "/items",
            json={"name": "Overflow Item", "category": "Tools", "replacement_value": overflow_val},
        )
        assert_error_envelope(r, 422)


def test_money_bounds_items_patch(client: TestClient):
    """PATCH /items/{id} replacement_value edge cases."""
    # Create valid item
    r_create = client.post(
        "/items",
        json={"name": "Base Tool", "category": "Tools", "replacement_value": 5000},
    )
    item_id = r_create.json()["id"]

    for bad_val in (0, -1, OVERFLOW_INT_32, OVERFLOW_INT_64, OVERFLOW_INT_BIG):
        r = client.patch(f"/items/{item_id}", json={"replacement_value": bad_val})
        assert_error_envelope(r, 422)

    # Valid update to MAX_DB_INT succeeds
    r_ok = client.patch(f"/items/{item_id}", json={"replacement_value": MAX_DB_INT})
    assert r_ok.status_code == 200
    assert r_ok.json()["replacement_value"] == MAX_DB_INT


def test_money_bounds_payments(client: TestClient):
    """POST /members/{id}/payments amount_paise edge cases."""
    # Member 1 exists from seed data
    for bad_val in (0, -1, OVERFLOW_INT_32, OVERFLOW_INT_64, OVERFLOW_INT_BIG):
        r = client.post("/members/1/payments", json={"amount_paise": bad_val})
        assert_error_envelope(r, 422)


# --- 2. ID Bounds (Path, Body, and Query) ---


def test_path_id_bounds(client: TestClient):
    """Every {id} path parameter rejects bad IDs with 422, and non-existent MAX_DB_INT with 404."""
    paths_and_methods = [
        ("GET", "/items/{id}"),
        ("PATCH", "/items/{id}", {"name": "Updated"}),
        ("POST", "/items/{id}/maintenance"),
        ("POST", "/items/{id}/restore-maintenance"),
        ("GET", "/members/{id}"),
        ("PATCH", "/members/{id}", {"name": "Updated"}),
        ("POST", "/members/{id}/suspend"),
        ("POST", "/members/{id}/reinstate"),
        ("POST", "/members/{id}/payments", {"amount_paise": 100}),
        ("GET", "/members/{id}/statement"),
        ("GET", "/loans/{id}"),
        ("POST", "/loans/{id}/checkout"),
        ("POST", "/loans/{id}/return"),
        ("POST", "/loans/{id}/cancel"),
    ]

    for entry in paths_and_methods:
        method = entry[0]
        template = entry[1]
        body = entry[2] if len(entry) > 2 else None

        # 0, -1, 2147483648, 2**63, 10**20 must return 422
        for bad_id in (0, -1, OVERFLOW_INT_32, OVERFLOW_INT_64, OVERFLOW_OFFSET):
            url = template.replace("{id}", str(bad_id))
            r = client.request(method, url, json=body)
            assert_error_envelope(r, 422)

        # MAX_DB_INT (2147483647) is a valid ID -> returns 404 Not Found (or 400/409, never 500)
        url_max = template.replace("{id}", str(MAX_DB_INT))
        r_max = client.request(method, url_max, json=body)
        err_msg = (
            f"Expected client error for non-existent ID on {method} {url_max}, "
            f"got {r_max.status_code}"
        )
        assert r_max.status_code in (404, 400, 409), err_msg
        assert_error_envelope(r_max, r_max.status_code)


def test_body_id_bounds_reserve(client: TestClient):
    """POST /loans/reserve member_id and item_id bounds."""
    for bad_id in (0, -1, OVERFLOW_INT_32, OVERFLOW_INT_64, OVERFLOW_OFFSET):
        # Invalid member_id
        r_m = client.post("/loans/reserve", json={"member_id": bad_id, "item_id": 1})
        assert_error_envelope(r_m, 422)

        # Invalid item_id
        r_i = client.post("/loans/reserve", json={"member_id": 1, "item_id": bad_id})
        assert_error_envelope(r_i, 422)


def test_query_filter_id_bounds(client: TestClient):
    """Query parameter ID filters on /loans and /loans/overdue."""
    endpoints = ["/loans", "/loans/overdue"]
    for ep in endpoints:
        for bad_id in (0, -1, OVERFLOW_INT_32, OVERFLOW_INT_64, OVERFLOW_OFFSET):
            r_m = client.get(f"{ep}?member_id={bad_id}")
            assert_error_envelope(r_m, 422)

            r_i = client.get(f"{ep}?item_id={bad_id}")
            assert_error_envelope(r_i, 422)


# --- 3. Pagination Bounds ---


def test_pagination_bounds(client: TestClient):
    """limit and offset bounds across all paginated endpoints."""
    endpoints = ["/items", "/members", "/loans", "/loans/overdue"]

    for ep in endpoints:
        # Invalid limits
        for bad_limit in (-1, OVERFLOW_INT_32, OVERFLOW_OFFSET):
            r = client.get(f"{ep}?limit={bad_limit}")
            assert_error_envelope(r, 422)

        # Invalid offsets
        for bad_offset in (-1, OVERFLOW_INT_32, OVERFLOW_OFFSET):
            r = client.get(f"{ep}?offset={bad_offset}")
            assert_error_envelope(r, 422)

        # Valid offset 0 and MAX_DB_INT accepted (200 OK)
        r_0 = client.get(f"{ep}?offset=0")
        assert r_0.status_code == 200

        r_max = client.get(f"{ep}?offset={MAX_DB_INT}")
        assert r_max.status_code == 200
        assert r_max.json() == []


# --- 4. Text Validation (NUL, Lone Surrogates, and Control Characters) ---


def test_text_rejects_nul_bytes(client: TestClient):
    """Reject NUL (0x00) bytes across text fields with 422, never 500."""
    # Member create
    r1 = client.post("/members", json={"name": "Alice\x00Smith", "phone": "+91-98765-43210"})
    assert_error_envelope(r1, 422)

    r2 = client.post("/members", json={"name": "Alice Smith", "phone": "+91-98765-\x00000"})
    assert_error_envelope(r2, 422)

    # Item create
    r3 = client.post(
        "/items",
        json={"name": "Tool\x00Name", "category": "Tools", "replacement_value": 1000},
    )
    assert_error_envelope(r3, 422)

    r4 = client.post(
        "/items",
        json={"name": "Tool Name", "category": "Tools\x00Bad", "replacement_value": 1000},
    )
    assert_error_envelope(r4, 422)

    r5 = client.post(
        "/items",
        json={
            "name": "Tool",
            "category": "Tools",
            "replacement_value": 1000,
            "condition_note": "Note\x00NUL",
        },
    )
    assert_error_envelope(r5, 422)

    # Payment note
    r6 = client.post("/members/1/payments", json={"amount_paise": 100, "note": "Payment\x00NUL"})
    assert_error_envelope(r6, 422)


def test_text_rejects_lone_surrogates(client: TestClient):
    """Reject lone surrogates that cannot be encoded as UTF-8."""
    raw_payload = b'{"name": "Bad \\ud800 Name", "phone": "+91-99999-11111"}'
    r = client.post("/members", content=raw_payload, headers={"Content-Type": "application/json"})
    assert_error_envelope(r, 422)


def test_single_line_text_rejects_control_characters(client: TestClient):
    """Single-line fields (name, category, phone) reject control characters like \\n and \\u0007."""
    for ctrl in ("\n", "\r", "\t", "\u0007", "\u001b"):
        # Member name
        r_name = client.post(
            "/members",
            json={"name": f"Alice{ctrl}Smith", "phone": "+91-99999-22222"},
        )
        assert_error_envelope(r_name, 422)

        # Member phone
        r_phone = client.post(
            "/members",
            json={"name": "Alice Smith", "phone": f"+91-99999{ctrl}22222"},
        )
        assert_error_envelope(r_phone, 422)

        # Item name and category
        r_item = client.post(
            "/items",
            json={"name": f"Saw{ctrl}1", "category": "Saws", "replacement_value": 1000},
        )
        assert_error_envelope(r_item, 422)

        r_cat = client.post(
            "/items",
            json={"name": "Saw 1", "category": f"Saws{ctrl}1", "replacement_value": 1000},
        )
        assert_error_envelope(r_cat, 422)


def test_notes_allow_newlines_and_tabs(client: TestClient):
    """Notes (condition_note, payment note) allow \\n and \\t."""
    # Item condition_note with \n and \t
    r_item = client.post(
        "/items",
        json={
            "name": "Multi-line Item",
            "category": "Tools",
            "replacement_value": 5000,
            "condition_note": "Line 1\nLine 2\n\tIndented details",
        },
    )
    assert r_item.status_code == 201
    assert "\n" in r_item.json()["condition_note"]

    # Payment note with \n and \t
    # Member 1 payment note
    r_pay = client.post(
        "/members/1/payments",
        json={"amount_paise": 100, "note": "Payment receipt:\nRef\t12345"},
    )
    # Status may be 201 or 400 (if overpayment), but never 422 or 500
    assert r_pay.status_code in (201, 400)


def test_unicode_accepted_scripts_and_emoji(client: TestClient):
    """Accepted multilingual scripts (Tamil, Hindi, Arabic, Sinhala, Persian) and emoji."""
    accepted_names = [
        "\u0dc1\u0dca\u200d\u0dbb\u0dd3 Perera",  # Sinhala (contains U+200D ZWJ)
        "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",  # Persian (contains U+200C ZWNJ)
        "Ravi \U0001f468\u200d\U0001f527",  # Emoji sequence with ZWJ
        "\u0b95\u0bcb\u0bb5\u0bc8",  # Tamil
        "\u0930\u093e\u092e",  # Hindi
        "\u0645\u062d\u0645\u062f",  # Arabic
        "Ravi \U0001fae9",  # Emoji newer than Python's Unicode tables (Cn category)
    ]
    for idx, name in enumerate(accepted_names, start=100):
        r = client.post(
            "/members",
            json={"name": name, "phone": f"+91-99999-{idx:05d}"},
        )
        assert r.status_code == 201, f"Failed for {name!r}: {r.text}"
        assert r.json()["name"] == name.strip()


def test_unicode_rejected_invisible_and_bidi_controls(client: TestClient):
    """Rejected invisible characters and bidi override controls (422 VALIDATION_ERROR)."""
    rejected_names = [
        "Ravi\u200bKumar",  # U+200B ZERO WIDTH SPACE
        "\ufeffRavi",  # U+FEFF ZERO WIDTH NO-BREAK SPACE / BOM
        "Ravi\u202eKumar",  # U+202E RIGHT-TO-LEFT OVERRIDE
        "Ravi\u2028Kumar",  # U+2028 LINE SEPARATOR
    ]
    for name in rejected_names:
        r = client.post(
            "/members",
            json={"name": name, "phone": "+91-99999-00000"},
        )
        assert_error_envelope(r, 422)


# --- 5. PATCH /items condition_note Behavior ---


def test_patch_item_condition_note_omitted(client: TestClient):
    """PATCH /items/{id} with condition_note omitted leaves the existing note unchanged."""
    r_create = client.post(
        "/items",
        json={
            "name": "Omit Tool",
            "category": "Tools",
            "replacement_value": 3000,
            "condition_note": "Initial Note",
        },
    )
    assert r_create.status_code == 201
    item_id = r_create.json()["id"]

    r_patch = client.patch(f"/items/{item_id}", json={"name": "Renamed Tool"})
    assert r_patch.status_code == 200
    assert r_patch.json()["condition_note"] == "Initial Note"


def test_patch_item_condition_note_null(client: TestClient):
    """PATCH /items/{id} with null condition_note preserves existing note."""
    r_create = client.post(
        "/items",
        json={
            "name": "Null Tool",
            "category": "Tools",
            "replacement_value": 3000,
            "condition_note": "Initial Note",
        },
    )
    assert r_create.status_code == 201
    item_id = r_create.json()["id"]

    r_patch = client.patch(f"/items/{item_id}", json={"condition_note": None})
    assert r_patch.status_code == 200
    assert r_patch.json()["condition_note"] == "Initial Note"


def test_patch_item_condition_note_empty_string(client: TestClient):
    """PATCH /items/{id} with condition_note '' clears the note to null."""
    r_create = client.post(
        "/items",
        json={
            "name": "Empty Tool",
            "category": "Tools",
            "replacement_value": 3000,
            "condition_note": "Initial Note",
        },
    )
    assert r_create.status_code == 201
    item_id = r_create.json()["id"]

    r_patch = client.patch(f"/items/{item_id}", json={"condition_note": ""})
    assert r_patch.status_code == 200
    assert r_patch.json()["condition_note"] is None


def test_patch_item_condition_note_whitespace_only(client: TestClient):
    """PATCH /items/{id} with condition_note '   ' clears the note to null."""
    r_create = client.post(
        "/items",
        json={
            "name": "Space Tool",
            "category": "Tools",
            "replacement_value": 3000,
            "condition_note": "Initial Note",
        },
    )
    assert r_create.status_code == 201
    item_id = r_create.json()["id"]

    r_patch = client.patch(f"/items/{item_id}", json={"condition_note": "   "})
    assert r_patch.status_code == 200
    assert r_patch.json()["condition_note"] is None


def test_patch_item_condition_note_updated_text(client: TestClient):
    """PATCH /items/{id} with condition_note 'x' updates the note to 'x'."""
    r_create = client.post(
        "/items",
        json={
            "name": "Update Tool",
            "category": "Tools",
            "replacement_value": 3000,
            "condition_note": "Initial Note",
        },
    )
    assert r_create.status_code == 201
    item_id = r_create.json()["id"]

    r_patch = client.patch(f"/items/{item_id}", json={"condition_note": "x"})
    assert r_patch.status_code == 200
    assert r_patch.json()["condition_note"] == "x"


# --- 6. Clock Header Robustness ---


def test_clock_header_robustness():
    """Extreme and hostile X-Test-Clock headers return 400 or valid, never 5xx."""
    from app.core.config import Settings

    settings = Settings(
        app_env="development",
        database_url=Settings.from_env().database_url,
        cors_origins=("http://localhost:5173",),
        log_level="INFO",
        allow_test_clock=True,
        test_clock_key="local-dev-clock-key-123456",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        clock_values = [
            ("9999-12-31T23:59:59Z", 422),
            ("0001-01-01T00:00:00Z", 422),
            ("2026-13-45T00:00:00Z", 422),
            ("A" * 5000, 422),
            ("10000000000-01-01T00:00:00Z", 422),
        ]

        for val, expected_st in clock_values:
            r = client.get(
                "/loans/overdue",
                headers={
                    "X-Test-Clock": val,
                    "X-Test-Clock-Key": "local-dev-clock-key-123456",
                },
            )
            assert r.status_code < 500
            assert_error_envelope(r, expected_st)

        # WRITE test: POST /loans/reserve with year 9999 clock is rejected
        # with 422 INVALID_TEST_CLOCK
        r_item = client.post(
            "/items",
            json={"name": "Clock Reserve Tool", "category": "Tools", "replacement_value": 2000},
        )
        assert r_item.status_code == 201
        clock_item_id = r_item.json()["id"]

        headers = {
            "X-Test-Clock": "9999-12-31T00:00:00Z",
            "X-Test-Clock-Key": "local-dev-clock-key-123456",
        }
        r_write = client.post(
            "/loans/reserve",
            json={"member_id": 1, "item_id": clock_item_id},
            headers=headers,
        )
        assert r_write.status_code == 422
        assert_error_envelope(r_write, 422)


# --- 7. Systematic OpenAPI Fuzzing ---


def test_systematic_openapi_hostile_parameters(client: TestClient):
    """Iterate over all OpenAPI routes, submitting hostile parameter values. Assert status < 500."""
    app = create_app()
    openapi_spec = app.openapi()
    hostile_values = [
        0,
        -1,
        2**31,
        2**63,
        10**20,
        "abc",
        "1e3",
        "%00",
        "",
        "A" * 5000,
        "🔧",
    ]

    for path, path_item in openapi_spec.get("paths", {}).items():
        # Skip test internal routes if any
        if path.startswith("/_test"):
            continue

        for method in ("get", "post", "patch", "put", "delete"):
            if method not in path_item:
                continue

            op = path_item[method]
            params = op.get("parameters", [])

            for hostile_val in hostile_values:
                test_path = path
                query_params = {}

                for p in params:
                    p_name = p["name"]
                    p_in = p["in"]
                    if p_in == "path":
                        test_path = test_path.replace(f"{{{p_name}}}", str(hostile_val))
                    elif p_in == "query":
                        query_params[p_name] = str(hostile_val)

                # Valid dummy body where request body is required
                json_body = None
                if "requestBody" in op:
                    json_body = {
                        "name": "Fuzz Item",
                        "category": "Fuzz Category",
                        "phone": "+91-99999-55555",
                        "replacement_value": 1000,
                        "amount_paise": 1000,
                        "member_id": 1,
                        "item_id": 1,
                    }

                resp = client.request(
                    method.upper(),
                    test_path,
                    params=query_params,
                    json=json_body,
                )
                assert (
                    resp.status_code < 500
                ), f"HTTP 500 on {method.upper()} {test_path} with {hostile_val}: {resp.text}"
                assert "Traceback" not in resp.text
                assert "psycopg" not in resp.text
                assert "SQL" not in resp.text
