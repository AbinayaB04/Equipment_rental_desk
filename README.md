## Title and one-liner

# Equipment Rental Desk
**Problem 1: Equipment Rental Desk — KJBN Labs Software Engineering Internship Take-Home Assignment**

A tool-library lending system designed to manage equipment reservations, check-outs, returns, overdue loans, late fees, member eligibility, payments, and suspensions.

**Repository:** [Equipment_rental_desk](https://github.com/AbinayaB04/Equipment_rental_desk)

**Current milestone:** M4 — User Interface (complete locally, commit pending)

> **Implementation status:** M0 scaffold, M1 domain models/migrations/seeds, M2 business rules/concurrency, and M3 REST APIs (including input robustness and test-clock hardening) are completed and committed (264 passing backend tests, 94% coverage). M4 UI is implemented and verified locally (26 frontend tests passing, browser walkthrough complete) but not yet committed. M5 deployment and M6 final documentation remain planned.

---

## Live links

### Local development using Docker Compose

| Service | URL |
|---|---|
| Frontend | http://localhost:8081 |
| Backend API | http://localhost:8001 |
| API documentation (Swagger UI) | http://localhost:8001/docs |
| OpenAPI schema | http://localhost:8001/openapi.json |
| PostgreSQL | `localhost:5434` |

These are local development URLs, not publicly deployed services.

**Deployment links:** Not available yet. Deployment is planned for a later milestone.

**Authentication:** The M0 scaffold does not implement authentication.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL 16 |
| Database access and migrations | SQLAlchemy 2.0, Alembic, and Psycopg (implemented in M1) |
| Frontend | React 18, TypeScript, Vite |
| Backend testing | pytest, pytest-cov, FastAPI TestClient |
| Linting and formatting | Ruff |
| Development hooks | pre-commit configuration |
| Containerization | Docker and Docker Compose |
| Version control | Git and GitHub |

The project uses a monorepo so the frontend, backend, tests, documentation, and deployment configuration can be maintained together.

---

## Architecture

The planned application architecture separates HTTP handling, business rules, application services, and database access.

```text
Browser
   |
   v
React + TypeScript + Vite
   |
   | HTTP / JSON
   v
FastAPI routes
   |
   v
Application services
   |
   +------> Domain rules and validation
   |
   v
Repositories / database access
   |
   v
PostgreSQL
```

### Project structure

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI application entry point |
| `backend/app/api/` | API routes, request/response schemas, and error handling |
| `backend/app/core/` | Configuration, clock, and logging utilities |
| `backend/app/domain/` | Pure business rules and domain logic |
| `backend/app/services/` | Use cases, transactions, and coordination of business operations |
| `backend/app/repositories/` | Database queries and persistence logic |
| `backend/app/models/` | Database models |
| `backend/migrations/` | Database migrations |
| `backend/scripts/` | Development and database scripts |
| `backend/tests/unit/` | Unit tests for individual rules and components |
| `backend/tests/api/` | API endpoint tests |
| `backend/tests/concurrency/` | Tests for concurrent state changes |
| `frontend/` | React, TypeScript, and Vite application |
| `docker-compose.yml` | Local multi-service configuration |
| `.env.example` | Example environment configuration |
| `PROMPTS.md` | AI prompt and usage log |
| `SUBMISSION.md` | Submission checklist and supporting information |

The `frontend/` directory contains the full M4 React/TypeScript/Vite application. Backend `scripts/` provides seed utilities. All other directories contain their intended production code.

### Why separate the layers?

Business rules should not depend directly on HTTP routes or browser behavior. Keeping them separate makes the rules easier to test, maintain, and explain during a code review or interview.

---

### Prerequisites

Install the following tools before running the project:

- Python 3.12
- Node.js 20 or newer
- npm
- Docker Desktop with Docker Compose
- Git

Verify the installations:

```powershell
py -3.12 --version
node --version
npm --version
docker --version
docker compose version
git --version
```

---

## Running locally

### Option A: Run the complete stack with Docker Compose

Run these commands from the repository root:

```powershell
cd D:\files\KJBN\Equipment_rental_desk
docker compose config
docker compose up --build -d
docker compose ps
```

The first command validates the resolved Compose configuration. The second builds and starts the services, and the third displays their status.

Check the backend health endpoint:

```powershell
Invoke-RestMethod http://localhost:8001/health
```

Expected response:

```json
{
  "status": "ok",
  "test_clock_enabled": false
}
```

Open the frontend in your browser:

http://localhost:8081

Open the interactive API documentation:

http://localhost:8001/docs

The PostgreSQL service is exposed on host port `5434`. The backend connects to PostgreSQL using the internal Compose service name and port.

To stop the services:

```powershell
docker compose down
```

To stop the services and delete the local database volume as well, use the following command **only if you intend to erase the local database data**:

```powershell
docker compose down -v
```

### Option B: Run the backend directly

Open PowerShell in the repository root:

```powershell
cd D:\files\KJBN\Equipment_rental_desk\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --port 8000
```

The API will be available at:

- Health: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs

This mode requires a suitable database configuration for any features that depend on PostgreSQL. The health endpoint returns service status and indicates whether the test clock is active.

### Option C: Run the frontend directly

Start the backend separately using the previous instructions, then open another PowerShell window:

```powershell
cd D:\files\KJBN\Equipment_rental_desk\frontend
npm ci
npm run dev
```

Vite will display the local frontend URL, normally:

http://localhost:5173

The development frontend should use the backend URL configured through `VITE_API_BASE_URL`. For direct local backend development, that is normally `http://localhost:8000`.

When running Docker Compose, the frontend build is configured to use `http://localhost:8001`.

---

### Environment configuration

The repository contains `.env.example` as a template. Keep real credentials and private keys out of Git.

| Variable | Purpose | Status |
|---|---|---|
| `APP_ENV` | Application environment, such as development, test, or production | M0 |
| `DATABASE_URL` | PostgreSQL connection string | Implemented in M1 |
| `CORS_ORIGINS` | Comma-separated list of permitted browser origins | M0 |
| `LOG_LEVEL` | Application logging level | M0 |
| `POSTGRES_USER` | Local PostgreSQL username | M1 |
| `POSTGRES_PASSWORD` | Local PostgreSQL password | M1 |
| `POSTGRES_DB` | Local PostgreSQL database name | M1 |
| `DB_PORT` | Host port mapped to PostgreSQL | M1 |
| `VITE_API_BASE_URL` | Backend URL used by the frontend | M0 |
| `ALLOW_TEST_CLOCK` | Enables the reviewer-controlled test clock | Implemented in M3 |
| `TEST_CLOCK_KEY` | Authorization key for test-clock use where required | Implemented in M3 |

The Docker Compose configuration uses its own service ports internally. Host port mappings can differ from container ports.

For the current Docker configuration, the intended host ports are:

- Frontend: `8081`
- Backend: `8001`
- PostgreSQL: `5434`

If you copy `.env.example` to `.env`, check that `DB_PORT` is set to `5434` to retain the current database port mapping.

Do not commit `.env` or real credentials.

---

## Running tests and coverage

### Backend tests

Run the following commands from the repository root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
ruff check .
ruff format --check .
pytest -q -rs
```

The test suite executes **264 passing tests** (0 skipped when PostgreSQL is available) across:
- **API and Route Integration:** Health check, origin CORS rules, member/item CRUD, loan reservation/checkout/return/cancel lifecycles, payments, member statements, overdue loans, input robustness (rejecting null bytes, out-of-range integers, and malformed strings with clean 422 errors instead of 5xx), and error envelope consistency (141 tests).
- **PostgreSQL Integration:** Schema check constraints, foreign key delete-restrictions, and sequence isolation (8 tests).
- **Concurrency Integration:** Thread-safe checkout, reservation, return, and payment operations against double-checkout and race conditions via `with_for_update()` (4 tests).
- **Transaction & Rollback Integration:** Caller-managed transaction boundaries, rollback safety on domain failures, and 2-phase settlement / outcome patterns for expired checkout (4 tests).
- **Business Rule Specifications:** 16 behavior-focused specification tests validating Problem 1 rules (active loan limit, 48h reservation expiry, 7-day loan duration, ₹10/day fee capped at ₹200 and replacement value, borrowing eligibility blocking on balance > ₹100 or overdue > 14 days, suspension).
- **Unit Tests:** Pure late-fee calculator (24h increments, caps), borrowing eligibility (suspension, balance, overdue > 14d, active loans), `LoanService`, `MemberService`, `ItemService`, test-clock settings validation, and clock window enforcement (58 tests).

When PostgreSQL is unavailable, PostgreSQL-specific integration and concurrency tests skip gracefully (211 passed, 20 skipped).

### Frontend tests and build

From the repository root:

```powershell
cd frontend
npm ci
npm test
npm run typecheck
npm run build
```

The test suite runs **26 frontend unit tests** covering utility functions, form validators, API client error handling, and query encoding — all passing. TypeScript checking (`tsc --noEmit`) and the production bundle build via Vite both complete without errors.

A live browser walkthrough against the running backend verified all frontend features end-to-end:
- Equipment Catalogue: item listing, search/filter, add item, set/restore maintenance.
- Member Directory: member listing, add member, suspend/reinstate, view statement, record payment.
- Loans & Reservations: reservation, checkout, return, cancellation, and overdue-loan filtering.

### Coverage

Generate a backend coverage report with:

```powershell
cd backend
pytest --cov=app --cov-report=term-missing
```

Backend statement coverage across `app` modules is **94%**, exceeding the target of at least 80% coverage. Frontend coverage is not collected separately; the 26 unit tests target the utility and validation layer.

---

## API overview

The following endpoints represent the implemented REST API surface:

| Method | Path | Purpose | Milestone |
|---|---|---|---|
| GET | `/health` | Health check and test-clock status | Implemented in M0, updated in M3 |
| GET, POST | `/members` | List and create members | Implemented in M3 |
| GET, PUT, DELETE | `/members/{id}` | Retrieve, update, and delete a member | Implemented in M3 |
| POST | `/members/{id}/suspend` | Suspend a member | Implemented in M3 |
| POST | `/members/{id}/reinstate` | Reinstate a member | Implemented in M3 |
| GET | `/members/{id}/eligibility` | Explain borrowing eligibility | Implemented in M3 |
| GET | `/members/{id}/statement` | View fees, payments, loans, and balance | Implemented in M3 |
| POST | `/members/{id}/payments` | Record a payment | Implemented in M3 |
| GET, POST | `/items` | List and create items | Implemented in M3 |
| GET, PUT, DELETE | `/items/{id}` | Retrieve, update, and delete an item | Implemented in M3 |
| POST | `/items/{id}/maintenance` | Place an item into maintenance | Implemented in M3 |
| POST | `/items/{id}/restore` | Restore an item from maintenance | Implemented in M3 |
| GET, POST | `/loans` | List loans and reserve an item (`POST /loans/reserve` supported) | Implemented in M3 |
| GET | `/loans/{id}` | Retrieve loan details | Implemented in M3 |
| GET | `/loans/overdue` | List overdue loans | Implemented in M3 |
| POST | `/loans/{id}/checkout` | Check out a reserved item | Implemented in M3 |
| POST | `/loans/{id}/return` | Return an item | Implemented in M3 |
| POST | `/loans/{id}/cancel` | Cancel a reservation | Implemented in M3 |

Interactive OpenAPI documentation is available at `/docs` (Swagger UI) and `/redoc`.

---

## Business rules and assumptions

The following table records the domain rules implemented and verified in M2 and M3.

| Rule | Implemented behavior | Status |
|---|---|---|
| Reservation expiry | Reservations expire after 48 hours | Implemented in M2/M3 |
| Loan duration | Seven days from check-out | Implemented in M2/M3 |
| Late fee | ₹10 per rounded-up 24-hour period, capped at ₹200 and replacement value | Implemented in M2/M3 |
| Active-loan limit | At most three active loans per member | Implemented in M2/M3 |
| Balance eligibility | A balance greater than ₹100 blocks borrowing | Implemented in M2/M3 |
| Long-overdue eligibility | A loan overdue by more than 14 days blocks borrowing | Implemented in M2/M3 |
| Member suspension | Suspended members cannot borrow | Implemented in M2/M3 |
| Payment validation | Payments cannot exceed the outstanding balance | Implemented in M2/M3 |
| Return validation | Only checked-out loans can be returned | Implemented in M2/M3 |
| Maintenance | Maintenance can coexist with an outstanding checked-out loan | Implemented in M2/M3 |
| Concurrency | Conflicting state changes use database transactions and consistent row locking | Implemented in M2/M3 |
| Test clock | Disabled by default and protected when enabled outside development/test | Implemented in M3 |

### Documented assumptions

1. **Reservation expiry:** A reservation holds an item for 48 hours. A reservation is valid at 47 hours 59 minutes and expired at exactly 48 hours (`now >= reserved_at + 48 hours`). An expired reservation's stored item status may temporarily remain `RESERVED` until M2 read/write logic reconciles it, but it is treated as effectively `AVAILABLE` on read and cannot be checked out.
2. **Late-fee calculation:** As an explicit interpretation of "calendar days, rounded up" for continuous timestamps, elapsed time past `due_at` is divided into 24-hour periods and rounded up. At `due_at` (0s overdue), fee is ₹0; 1 second overdue incurs 1 day (₹10); exactly 24 hours late incurs 1 day (₹10); 24 hours and 1 second late incurs 2 days (₹20). The fee is capped at ₹200 (20,000 paise) and never exceeds the item's replacement value.
3. **Due date:** The due time is the check-out time plus exactly seven days.
4. **Outstanding fees:** An overdue loan does not add its late fee to the member balance until it is returned.
5. **Balance:** The balance is derived from returned-loan fees minus payments. Overpayments are rejected; credit balances are not created.
6. **Maintenance:** When an item enters maintenance: if the item was `RESERVED`, the reservation is cancelled (`Loan.status = CANCELLED`, `cancelled_at = now`). If the item was `CHECKED_OUT`, the open loan remains valid and returnable. Upon return, late fees (if any) are assessed and the loan is closed, but the item remains `UNDER_MAINTENANCE` until staff restores it to `AVAILABLE`.
7. **Active-loan limit:** The limit is checked at reservation time. Checking out an existing reservation does not add another active loan.
8. **Long-overdue threshold:** A loan blocks borrowing only when it is overdue by more than 14 days; exactly 14 days does not exceed the threshold.
9. **Eligibility:** Eligibility is checked at reservation and checked again at check-out.
10. **Deletion:** Members and items with associated loans or payments cannot be deleted; the API returns a conflict response.
11. **Authentication:** Staff operations are implemented as standard REST endpoints per assignment specifications. The reviewer test clock is secured with key-based authorization in production.
12. **Phone numbers:** Member phone numbers are stored as strings without arbitrary database-level uniqueness or regex format constraints, as the assignment does not require phone uniqueness across members (e.g. household members sharing a contact number).
13. **Monotonic clock guard:** History-changing item operations compare the request time with the latest relevant loan event timestamps and `maintenance_changed_at`. Earlier times are rejected. Read-only requests, payments, suspensions, and ordinary CRUD edits are not subject to this guard.
14. **Restore behavior:** Restoring an item settles an expired reservation in the same transaction and does not fail solely because an expired reservation row still has stored status `reserved`.
15. **Expired reservations:** Expired reservations do not count towards the active-loan limit or prevent a new reservation once they have been safely settled.
16. **Replacement-value cap:** The replacement value used for the late-fee cap is the item's value at return time.
17. **Overdue boundary:** A loan becomes overdue strictly after `due_at`, not at the exact due time.
18. **Unknown IDs:** Unknown member or item IDs supplied to relevant requests produce a not-found response (404).
19. **Read-only GET requests:** GET requests do not update or clean up reservation records. Expired-reservation cleanup happens transactionally during relevant write operations.

---

## Error handling and logging

The backend implements centralized, RFC-compliant error responses and consistent HTTP status mappings with structured logging and `X-Request-ID` propagation.

Implemented HTTP status codes include:

| Status | Meaning |
|---|---|
| `400` | Malformed request or numeric overflow safety net |
| `403` | Member is not eligible for the requested operation, or test clock is disabled / unauthorized |
| `404` | Resource not found |
| `409` | State conflict, such as an expired reservation or duplicate action |
| `422` | Validation error, invalid test clock outside allowed window, or payment exceeding outstanding balance |
| `503` | Temporary lock contention, with `Retry-After` for a `BUSY` response |
| `500` | Unexpected server error, without exposing internal stack traces or database driver details |

State-changing operations use database transactions and pessimistic row locking (`with_for_update()`). This prevents duplicate check-outs, double returns, inconsistent item/loan states, and race conditions during concurrent requests. Implemented exception handlers in `app/api/errors.py` capture `DomainError`, `RequestValidationError`, `IntegrityError`, `DataError`, `OverflowError`, and `TestClockError`.

---

## Reviewer aids

**Status:** Implemented and hardened in M3.

The reviewer-controlled test clock allows verifying time-dependent business rules (such as 48-hour reservation expiry and overdue loan fees) deterministically.

Key design attributes:
- **Disabled by default:** `ALLOW_TEST_CLOCK=false`. Unset `APP_ENV` defaults to production.
- **Production security:** When `ALLOW_TEST_CLOCK=true` in production, `TEST_CLOCK_KEY` (minimum 16 characters) is strictly required. The application fails fast and refuses to start if misconfigured.
- **Request-scoped:** Passed per-request via the `X-Test-Clock` header (ISO-8601 UTC timestamp). When key authorization is enabled, the reviewer provides `X-Test-Clock-Key` or `Authorization: Bearer <key>`, validated using constant-time `hmac.compare_digest`.
- **Bounded window:** To prevent integer/date-math overflows, simulated timestamps must be within **±90 days** (`TEST_CLOCK_MAX_OFFSET = timedelta(days=90)`) of actual server time. Values outside this window are rejected with HTTP 422 `INVALID_TEST_CLOCK`.
- **Visibility:** Responses produced under a simulated clock include the response header `X-Clock-Mode: test` (exposed via CORS `expose_headers`). The `/health` endpoint exposes `{"status": "ok", "test_clock_enabled": <bool>}`.
- **Audit logging:** Each simulated clock usage logs a WARNING containing the `request_id` and simulated time (never exposing keys or secrets).

---

## Deployment

**Status:** Pending (Planned for M5). No public cloud deployment is claimed at this stage.

The intended deployment approach is:

- PostgreSQL: Neon or another PostgreSQL-compatible managed service.
- Backend: Render or another platform that supports the backend container.
- Frontend: Vercel or another static frontend host.

Local deployment via Docker Compose is fully operational on ports 8001 (backend), 8081 (frontend), and 5434 (PostgreSQL). Live public URLs, environment configurations, and deployment steps will be documented once M5 is executed and verified.

---

## Known limitations

- **Frontend commit (M4):** The full M4 user interface is implemented and verified locally (Equipment Catalogue, Member Directory, Loans & Reservations, statements, payments, maintenance, overdue loans). The changes are not yet committed to the repository.
- **Cloud Deployment (M5):** The stack runs locally via Docker Compose and standalone processes; public cloud hosting is pending.
- **v1.0 Git Tag:** No `v1.0` tag exists yet; the tag will be created upon completion and verification of all submission deliverables.

---

## AI and third-party usage

AI-assisted development and review tools used for this project include:

| Tool | Purpose |
|---|---|
| Claude | Assignment analysis, design planning, design review, and initial scaffold/documentation assistance |
| Google Antigravity | Comparison, review of project files, backend fix implementations, and prompt log maintenance |

The detailed AI prompt log is maintained in [`PROMPTS.md`](./PROMPTS.md).

### Third-party libraries

The project uses libraries including FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, psycopg, pytest, pytest-cov, httpx, Ruff, React, Vite, and TypeScript.

---

### Submission and milestones

The project is organized into seven milestones, M0–M6, following the assignment requirements.

| Milestone | Focus | Status |
|---|---|---|
| M0 | Scaffold, health endpoint, frontend build, Docker Compose, documentation | Complete (commit `2f56c06`) |
| M1 | Database schema, migrations, and seed data | Complete (commit `e039207`) |
| M2 | Domain rules and unit tests | Complete (commit `dfe8100`) |
| M3 | API endpoints, validation, transactions, and concurrency | Complete (commits `4e69879`, `ddeb960`) |
| M4 | User interface (React, TypeScript, Vite) | Complete locally (commit pending) |
| M5 | Deployment and deployment documentation | Planned |
| M6 | Final coverage report, review, and submission cleanup | Planned |

The final milestone scope and naming follow the assignment's exact requirements.

See [`SUBMISSION.md`](./SUBMISSION.md) for the submission checklist and write-up.

---

### License

This repository was created for the KJBN Labs Software Engineering Internship take-home assignment. No separate open-source license has been declared.
