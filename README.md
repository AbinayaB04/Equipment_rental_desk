# Equipment Rental Desk

**Problem 1: Equipment Rental Desk — KJBN Labs Software Engineering Internship Take-Home Assignment**

A full-stack tool-library lending system for equipment reservations, check-outs, returns, overdue loans, late fees, member eligibility, payments, and suspensions.

**Repository:** [Equipment_rental_desk](https://github.com/AbinayaB04/Equipment_rental_desk)

**Current milestone:** M6 — Final verification and submission documentation completed.

**Implementation status:** M0–M6 implementation and documentation work is complete. The frontend is deployed on Vercel, the FastAPI backend on Render, and PostgreSQL is hosted on Neon. Database migrations run during backend startup. The application and documentation are ready for final release verification. The `v1.0` tag must be confirmed or created as the final release step.

---

## Live links

| Service | URL |
|---|---|
| Frontend | https://equipment-rental-desk-eight.vercel.app/ |
| Backend API | https://equipment-rental-desk.onrender.com |
| Health check | https://equipment-rental-desk.onrender.com/health |
| API documentation (Swagger UI) | https://equipment-rental-desk.onrender.com/docs |
| OpenAPI schema | https://equipment-rental-desk.onrender.com/openapi.json |
| Source repository | https://github.com/AbinayaB04/Equipment_rental_desk |

**Deployment architecture:** Vercel hosts the frontend, Render hosts the FastAPI backend, and Neon provides managed PostgreSQL. The backend is configured to apply Alembic migrations at startup. Do not expose database credentials or other secrets in the repository or documentation.

### Local development using Docker Compose

| Service | URL |
|---|---|
| Frontend | http://localhost:8081 |
| Backend API | http://localhost:8001 |
| API documentation | http://localhost:8001/docs |
| OpenAPI schema | http://localhost:8001/openapi.json |
| PostgreSQL | `localhost:5434` |

The local Compose setup is separate from the public deployment. General staff authentication and role-based access control are not implemented.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL 16 |
| Database access and migrations | SQLAlchemy 2.0, Alembic, Psycopg |
| Frontend | React 18, TypeScript, Vite |
| Backend testing | pytest, pytest-cov, FastAPI TestClient |
| Linting and formatting | Ruff |
| Development hooks | pre-commit configuration |
| Containerization | Docker and Docker Compose |
| Version control | Git and GitHub |
| Deployment | Render, Neon, Vercel |

The project uses a monorepo so the frontend, backend, tests, documentation, and deployment configuration can be maintained together.

---

## Architecture

The application separates HTTP handling, business rules, application services, and database access.

```text
Browser
   |
   v
React + TypeScript + Vite
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
| `backend/app/domain/` | Business rules and domain logic |
| `backend/app/services/` | Use cases, transactions, and business-operation coordination |
| `backend/app/repositories/` | Database queries and persistence logic |
| `backend/app/models/` | Database models |
| `backend/migrations/` | Database migrations |
| `backend/scripts/` | Development and database scripts |
| `backend/tests/unit/` | Unit tests |
| `backend/tests/api/` | API endpoint tests |
| `backend/tests/concurrency/` | Concurrent state-change tests |
| `frontend/` | React, TypeScript, and Vite application |
| `docker-compose.yml` | Local multi-service configuration |
| `.env.example` | Example environment configuration |
| `PROMPTS.md` | AI prompt and usage log |
| `SUBMISSION.md` | Submission write-up |

Separating business rules from HTTP routes and browser behavior makes the rules easier to test, maintain, and review.

---

## Prerequisites

Install Python 3.12, Node.js 20 or newer, npm, Docker Desktop with Docker Compose, and Git.

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
docker compose config
docker compose up --build -d
docker compose ps
```

Check backend health:

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

Open the frontend at http://localhost:8081 and the API documentation at http://localhost:8001/docs.

The PostgreSQL service is exposed on host port `5434`; the backend uses the internal Compose service name and port.

Stop the services:

```powershell
docker compose down
```

To also delete the local database volume, run this only if you intend to erase the local database data:

```powershell
docker compose down -v
```

### Option B: Run the backend directly

Open PowerShell in the repository root:

```powershell
cd backend
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

This mode requires a correctly configured PostgreSQL database. Use a local development database or another database explicitly intended for development; do not run seed commands against production unintentionally.

### Option C: Run the frontend directly

Start the backend separately, then open another PowerShell window:

```powershell
cd frontend
npm ci
npm run dev
```

Vite displays the frontend URL, normally http://localhost:5173.

Configure `VITE_API_BASE_URL` to point to the backend. For direct local backend development, use `http://localhost:8000`; for the Docker Compose setup, the frontend is configured to use `http://localhost:8001`.

---

## Environment configuration

The repository contains `.env.example` as a template. Keep real credentials and private keys out of Git.

| Variable | Purpose |
|---|---|
| `APP_ENV` | Application environment |
| `DATABASE_URL` | PostgreSQL connection string |
| `CORS_ORIGINS` | Comma-separated permitted browser origins |
| `LOG_LEVEL` | Application logging level |
| `POSTGRES_USER` | Local PostgreSQL username |
| `POSTGRES_PASSWORD` | Local PostgreSQL password |
| `POSTGRES_DB` | Local PostgreSQL database name |
| `DB_PORT` | Host port mapped to PostgreSQL |
| `VITE_API_BASE_URL` | Backend URL used by the frontend |
| `ALLOW_TEST_CLOCK` | Enables the reviewer-controlled test clock |
| `TEST_CLOCK_KEY` | Authorization key for test-clock use where required |

The current Docker configuration uses these host ports:

- Frontend: `8081`
- Backend: `8001`
- PostgreSQL: `5434`

If you copy `.env.example` to `.env`, ensure `DB_PORT` matches the Compose configuration. Host port mappings can differ from container ports.

For cloud deployment, configure environment variables through the relevant hosting provider's settings. Never commit `.env` files or real credentials.

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

The last previously reported test results were **264 passing backend tests**, with zero skipped when PostgreSQL was available. Tests cover:

- API integration, CRUD operations, reservations, checkout, returns, payments, statements, overdue loans, validation, and error responses.
- PostgreSQL constraints, foreign-key delete restrictions, and sequence isolation.
- Concurrent checkout, reservation, return, and payment operations.
- Transaction boundaries and rollback safety.
- Business rules, including the active-loan limit, 48-hour reservation expiry, seven-day loan duration, late-fee caps, eligibility, and suspension.
- Unit tests for fee calculation, eligibility, services, and test-clock validation.

When PostgreSQL is unavailable, PostgreSQL-dependent tests may skip. Run the suite against PostgreSQL before reporting the final results.

### Frontend tests and build

From the repository root:

```powershell
cd frontend
npm ci
npm test
npm run typecheck
npm run build
```

The last previously reported results were **26 passing frontend tests**, with TypeScript checking and the Vite production build completing successfully. Tests cover utility functions, form validation, API client error handling, and query encoding.

The frontend workflows include:

- **Equipment catalogue:** listing, searching/filtering, adding items, and maintenance actions.
- **Member directory:** listing and adding members, suspension/reinstatement, statements, and payments.
- **Loans and reservations:** reservation, checkout, return, cancellation, and overdue-loan filtering.

### Coverage

Generate the backend coverage report:

```powershell
cd backend
pytest --cov=app --cov-report=term-missing
```

The last reported backend statement coverage was **94%**, above the assignment target of at least 80%. These are previously reported results; refresh the report if updated coverage evidence is required for the final submission. Frontend coverage is not collected separately.

---

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check and test-clock status |
| GET, POST | `/members` | List and create members |
| GET, PUT, DELETE | `/members/{id}` | Retrieve, update, and delete a member |
| POST | `/members/{id}/suspend` | Suspend a member |
| POST | `/members/{id}/reinstate` | Reinstate a member |
| GET | `/members/{id}/eligibility` | Explain borrowing eligibility |
| GET | `/members/{id}/statement` | View fees, payments, loans, and balance |
| POST | `/members/{id}/payments` | Record a payment |
| GET, POST | `/items` | List and create items |
| GET, PUT, DELETE | `/items/{id}` | Retrieve, update, and delete an item |
| POST | `/items/{id}/maintenance` | Place an item into maintenance |
| POST | `/items/{id}/restore` | Restore an item from maintenance |
| GET, POST | `/loans` | List loans and create reservations |
| GET | `/loans/{id}` | Retrieve loan details |
| GET | `/loans/overdue` | List overdue loans |
| POST | `/loans/{id}/checkout` | Check out a reserved item |
| POST | `/loans/{id}/return` | Return an item |
| POST | `/loans/{id}/cancel` | Cancel a reservation |

The interactive API documentation is available at `/docs` (Swagger UI) and `/redoc`.

---

## Business rules and assumptions

| Rule | Implemented behavior |
|---|---|
| Reservation expiry | Reservations expire after 48 hours |
| Loan duration | Seven days from check-out |
| Late fee | ₹10 per rounded-up 24-hour period, capped at ₹200 and replacement value |
| Active-loan limit | At most three active loans per member |
| Balance eligibility | A balance greater than ₹100 blocks borrowing |
| Long-overdue eligibility | A loan overdue by more than 14 days blocks borrowing |
| Member suspension | Suspended members cannot borrow |
| Payment validation | Payments cannot exceed the outstanding balance |
| Return validation | Only checked-out loans can be returned |
| Maintenance | An outstanding checked-out loan remains returnable while its item is under maintenance |
| Concurrency | Database transactions and row locking protect conflicting state changes |
| Test clock | Disabled by default and protected when enabled outside development/test |

### Documented assumptions

1. **Reservation expiry:** A reservation expires at exactly 48 hours (`now >= reserved_at + 48 hours`). Expired reservations are treated as available in reads and reconciled during relevant write operations.
2. **Late-fee calculation:** Elapsed time past `due_at` is divided into 24-hour periods and rounded up. One second overdue incurs ₹10; exactly 24 hours late incurs ₹10; 24 hours and one second late incurs ₹20. The fee is capped at ₹200 and the item's replacement value.
3. **Due date:** The due time is check-out time plus exactly seven days.
4. **Outstanding fees:** Late fees for an overdue loan are assessed when the item is returned.
5. **Balance:** Balance is derived from returned-loan fees minus payments. Overpayments are rejected.
6. **Maintenance:** A reserved item entering maintenance has its reservation cancelled. A checked-out item remains returnable; after return, it stays under maintenance until staff restores it.
7. **Active-loan limit:** The limit is checked when reserving. Checking out an existing reservation does not create another active loan.
8. **Long-overdue threshold:** Borrowing is blocked only when a loan is overdue by more than 14 days.
9. **Eligibility:** Eligibility is checked at reservation and again at checkout.
10. **Deletion:** Members and items with associated loans or payments cannot be deleted; the API returns a conflict response.
11. **Authentication:** Staff operations use standard REST endpoints. The reviewer test clock has key-based authorization when required; general staff authentication is not implemented.
12. **Phone numbers:** Phone numbers are stored as strings and are not required to be unique.
13. **Monotonic clock guard:** History-changing item operations reject request times earlier than relevant loan events or maintenance changes. Read-only requests and unrelated operations are not subject to this guard.
14. **Restore behavior:** Restoring an item safely handles expired reservations within the transaction.
15. **Expired reservations:** Expired reservations do not count towards the active-loan limit after they have been safely settled.
16. **Replacement-value cap:** The replacement value used for the late-fee cap is the item's value at return time.
17. **Overdue boundary:** A loan becomes overdue strictly after `due_at`.
18. **Unknown IDs:** Requests referencing unknown member or item IDs return HTTP 404.
19. **Read-only GET requests:** GET requests do not modify reservation records; cleanup occurs during relevant write operations.

---

## Error handling and logging

The backend implements centralized error responses, consistent HTTP status mappings, structured logging, and `X-Request-ID` propagation.

| Status | Meaning |
|---|---|
| `400` | Malformed request or numeric overflow safety net |
| `403` | Operation not permitted, or test clock disabled/unauthorized |
| `404` | Resource not found |
| `409` | State conflict, such as an expired reservation or duplicate action |
| `422` | Validation failure, invalid test-clock window, or payment exceeding outstanding balance |
| `503` | Temporary lock contention, with `Retry-After` for a `BUSY` response |
| `500` | Unexpected server error without exposing internal details |

State-changing operations use database transactions and pessimistic row locking (`with_for_update()`). Exception handlers cover domain errors, request validation, database integrity/data errors, overflow errors, and test-clock errors.

---

## Reviewer aids

The reviewer-controlled test clock supports deterministic testing of time-dependent rules, including reservation expiry and overdue fees.

- **Disabled by default:** `ALLOW_TEST_CLOCK=false`.
- **Production security:** Enabling it in production requires a `TEST_CLOCK_KEY` of at least 16 characters; invalid configuration prevents startup.
- **Request-scoped:** Supplied through the `X-Test-Clock` header as an ISO-8601 timestamp. Key authorization uses `X-Test-Clock-Key` or a bearer token where configured.
- **Bounded window:** Simulated times must be within ±90 days of server time; out-of-range values return HTTP 422.
- **Visibility:** Simulated-clock responses include `X-Clock-Mode: test`. The `/health` endpoint reports whether the test clock is enabled.
- **Audit logging:** Clock usage is logged with a request ID and simulated time, without logging secrets.

---

## Deployment

**Status:** Deployed; M6 documentation work is complete. Confirm the release tag separately.

- **Frontend:** Vercel — https://equipment-rental-desk-eight.vercel.app/
- **Backend:** Render — https://equipment-rental-desk.onrender.com
- **Database:** Neon PostgreSQL
- **Migrations:** Alembic migrations run during backend startup.
- **Local stack:** Docker Compose runs the frontend, backend, and PostgreSQL on the configured local ports.

Check the backend health endpoint and API documentation after deployment. Confirm the frontend can load data from the backend, and verify that cloud environment variables are configured in the provider dashboards rather than committed to Git.

---

## Known limitations

- **Authentication:** General staff authentication and role-based access control are not implemented.
- **Frontend coverage:** Frontend unit tests exist, but a separate frontend coverage report is not collected.
- **Test evidence:** The test and coverage figures in this document are the last previously reported results, not a new test run performed during this documentation update.

---

## AI and third-party usage

AI-assisted development and review tools used for this project include:

| Tool | Purpose |
|---|---|
| Claude | Assignment analysis, design planning, design review, and initial scaffold/documentation assistance |
| Google Antigravity | Project-file review, backend fixes, and prompt-log maintenance |

The detailed AI prompt log is maintained in [`PROMPTS.md`](./PROMPTS.md).

### Third-party libraries

The project uses libraries including FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, Psycopg, pytest, pytest-cov, httpx, Ruff, React, Vite, and TypeScript.

---

## Submission and milestones

The project follows the assignment's seven milestones, M0–M6. M6 documentation updates have been committed and pushed; verify the `v1.0` release tag separately.

| Milestone | Focus | Status |
|---|---|---|
| M0 | Scaffold, health endpoint, frontend build, Docker Compose, documentation | Complete — `2f56c06` |
| M1 | Database schema, migrations, and seed data | Complete — `e039207` |
| M2 | Domain rules and unit tests | Complete — `dfe8100` |
| M3 | API endpoints, validation, transactions, and concurrency | Complete — `4e69879`, `ddeb960` |
| M4 | React, TypeScript, and Vite user interface | Complete — `f3b248b`, `5e1e6a7` |
| M5 | Deployment and startup migrations | Deployed — `dfb56a7` |
| M6 | Final documentation and submission preparation | Documentation committed and pushed — `7dec8cf`; release tag to verify |



See [`SUBMISSION.md`](./SUBMISSION.md) for the submission write-up.

---

