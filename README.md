# Equipment Rental Desk

**Problem 1: Equipment Rental Desk — KJBN Labs Software Engineering Internship Take-Home Assignment**

A tool-library lending system designed to manage equipment reservations, check-outs, returns, overdue loans, late fees, member eligibility, payments, and suspensions.

**Repository:** [Equipment_rental_desk](https://github.com/AbinayaB04/Equipment_rental_desk)

**Current milestone:** M0 — Project scaffold

> **Implementation status:** M0 provides the initial project structure, FastAPI health endpoint, React frontend scaffold, Docker Compose setup, and development checks. Business rules and API endpoints for later milestones are planned and are not yet implemented. This README will be updated as each milestone is completed.

---

## 1. Live Links and Local URLs

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

## 2. Technology Stack

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

## 3. Architecture

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

Some directories are currently scaffolding placeholders. They will be populated as implementation progresses.

### Why separate the layers?

Business rules should not depend directly on HTTP routes or browser behavior. Keeping them separate makes the rules easier to test, maintain, and explain during a code review or interview.

---

## 4. Prerequisites

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

## 5. Running the Application Locally

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
  "status": "ok"
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

This mode requires a suitable database configuration for any features that depend on PostgreSQL. The M0 health endpoint does not require the later database functionality.

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

## 6. Environment Configuration

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
| `ALLOW_TEST_CLOCK` | Enables the reviewer-controlled test clock | Planned for M3 |
| `TEST_CLOCK_KEY` | Authorization key for test-clock use where required | Planned for M3 |

The Docker Compose configuration uses its own service ports internally. Host port mappings can differ from container ports.

For the current Docker configuration, the intended host ports are:

- Frontend: `8081`
- Backend: `8001`
- PostgreSQL: `5434`

If you copy `.env.example` to `.env`, check that `DB_PORT` is set to `5434` to retain the current database port mapping.

Do not commit `.env` or real credentials.

---

## 7. Testing and Code Quality

### Backend tests

Run the following commands from the repository root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
ruff check .
ruff format --check .
pytest -q
```

The default test run executes **14 passing tests** (3 API health checks, 3 environment configuration checks, and 8 PostgreSQL schema constraint tests verifying check constraints and foreign key rules).

To inspect the M2 business-rule behavioral specification contracts:

```powershell
pytest tests/unit/test_business_rules_spec.py -m m2_spec
```

*Note on M2 specifications:* These 16 behavioral specification tests define the business rule contracts for Milestone 2. They are expected to fail until M2 implements the service layer, and are excluded from the default M1 test run to prevent breaking test collection.

### Frontend build

From the repository root:

```powershell
cd frontend
npm ci
npm run build
```

The build runs TypeScript checking and generates the production frontend bundle.

### Coverage

Generate a backend coverage report with:

```powershell
cd backend
pytest --cov=app --cov-report=term-missing
```

Coverage results for the complete business-rule implementation will be reported after the relevant functionality and tests are implemented. No final coverage percentage is claimed at M0.

The target is at least 80% coverage of business rules, subject to the assignment's exact coverage requirements.

---

## 8. API Overview

Only `GET /health` is implemented in M0. The following endpoints describe the planned API surface and will be updated as each endpoint is implemented and tested.

| Method | Planned path | Purpose | Milestone |
|---|---|---|---|
| GET | `/health` | Health check | M0 |
| GET, POST | `/members` | List and create members | Planned M3 |
| GET, PUT, DELETE | `/members/{id}` | Retrieve, update, and delete a member | Planned M3 |
| POST | `/members/{id}/suspend` | Suspend a member | Planned M3 |
| POST | `/members/{id}/reinstate` | Reinstate a member | Planned M3 |
| GET | `/members/{id}/eligibility` | Explain borrowing eligibility | Planned M3 |
| GET | `/members/{id}/statement` | View fees, payments, loans, and balance | Planned M3 |
| POST | `/members/{id}/payments` | Record a payment | Planned M3 |
| GET, POST | `/items` | List and create items | Planned M3 |
| GET, PUT, DELETE | `/items/{id}` | Retrieve, update, and delete an item | Planned M3 |
| POST | `/items/{id}/maintenance` | Place an item into maintenance | Planned M3 |
| POST | `/items/{id}/restore` | Restore an item from maintenance | Planned M3 |
| GET, POST | `/loans` | List loans and reserve an item | Planned M3 |
| GET | `/loans/{id}` | Retrieve loan details | Planned M3 |
| GET | `/loans/overdue` | List overdue loans | Planned M3 |
| POST | `/loans/{id}/checkout` | Check out a reserved item | Planned M3 |
| POST | `/loans/{id}/return` | Return an item | Planned M3 |
| POST | `/loans/{id}/cancel` | Cancel a reservation | Planned M3 |

API paths and response schemas will be confirmed against the assignment specification during implementation.

---

## 9. Business Rules and Design Assumptions

The following table records the planned rules. They are design decisions and are not all implemented in M0.

| Rule | Planned behavior | Status |
|---|---|---|
| Reservation expiry | Reservations expire after 48 hours | Planned |
| Loan duration | Seven days from check-out | Planned |
| Late fee | ₹10 per rounded-up 24-hour period, capped at ₹200 and replacement value | Planned |
| Active-loan limit | At most three active loans per member | Planned |
| Balance eligibility | A balance greater than ₹100 blocks borrowing | Planned |
| Long-overdue eligibility | A loan overdue by more than 14 days blocks borrowing | Planned |
| Member suspension | Suspended members cannot borrow | Planned |
| Payment validation | Payments cannot exceed the outstanding balance | Planned |
| Return validation | Only checked-out loans can be returned | Planned |
| Maintenance | Maintenance can coexist with an outstanding checked-out loan | Planned |
| Concurrency | Conflicting state changes use database transactions and consistent row locking | Planned |
| Test clock | Disabled by default and protected when enabled outside development/test | Planned |

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
10. **Deletion:** Members and items with associated loans or payments cannot be deleted; the planned API returns a conflict response.
11. **Authentication:** Authentication is not included in the M0 scaffold. Staff operations are planned as ordinary API endpoints unless the assignment requires otherwise.
12. **Phone numbers:** Member phone numbers are stored as strings without arbitrary database-level uniqueness or regex format constraints, as the assignment does not require phone uniqueness across members (e.g. household members sharing a contact number).
13. **Monotonic clock guard:** History-changing item operations compare the request time with the latest relevant loan event timestamps and `maintenance_changed_at`. Earlier times are rejected. Read-only requests, payments, suspensions, and ordinary CRUD edits are not subject to this guard.
14. **Restore behavior:** Restoring an item must first settle an expired reservation in the same transaction and must not fail solely because an expired reservation row still has stored status `reserved`.
15. **Expired reservations:** Expired reservations must not count towards the active-loan limit or prevent a new reservation once they have been safely settled.
16. **Replacement-value cap:** The replacement value used for the late-fee cap is the item's value at return time.
17. **Overdue boundary:** A loan becomes overdue strictly after `due_at`, not at the exact due time.
18. **Unknown IDs:** Unknown member or item IDs supplied to relevant requests should produce a not-found response.
19. **Read-only GET requests:** GET requests must not update or clean up reservation records. Expired-reservation cleanup happens transactionally during relevant write operations.

These assumptions will be validated against the assignment specification and covered by tests as the relevant milestones are implemented.

---

## 10. Error Handling and Concurrency

The planned API will use consistent error responses. The final response schemas will be documented when the API is implemented.

Planned HTTP status codes include:

| Status | Meaning |
|---|---|
| `403` | Member is not eligible for the requested operation |
| `404` | Resource not found |
| `409` | State conflict, such as an expired reservation |
| `422` | Invalid input or payment exceeding the outstanding balance |
| `503` | Temporary lock contention, with `Retry-After` for a `BUSY` response |
| `500` | Unexpected server error, without exposing internal stack traces |

State-changing operations will use database transactions and a consistent locking strategy. The goal is to prevent duplicate check-outs, double returns, inconsistent item/loan states, and conflicting payments.

This behavior is planned and is not yet implemented in M0.

---

## 11. Reviewer Test Clock

A reviewer-controlled test clock is planned for M3.

The intended design is:

- Disabled by default through `ALLOW_TEST_CLOCK=false`.
- Authorized when enabled outside development/test using `TEST_CLOCK_KEY`.
- Request-scoped, using the `X-Test-Clock` header and an authorization header when required.
- Applied to one request at a time.
- Excluded from normal read-only request validation that checks event-time monotonicity.
- Tested to ensure it cannot be enabled or used accidentally.

The final header behavior and reviewer instructions will be documented once implemented.

---

## 12. Deployment

**Status:** Planned; no public deployment is claimed at M0.

The intended deployment approach is:

- PostgreSQL: Neon or another PostgreSQL-compatible managed service.
- Backend: Render or another platform that supports the backend container.
- Frontend: Vercel or another static frontend host.

The final deployment section will include actual live URLs, required environment variables, database migration and seed instructions, and redeployment steps after deployment has been completed and verified.

---

## 13. Known Limitations at M0

- The application currently provides a health endpoint and a frontend scaffold.
- Member, item, loan, payment, maintenance, and suspension operations are not yet implemented.
- Database migrations and seed data are planned for M1.
- Business rules, transaction locking, and the test clock are planned for later milestones.
- Public deployment has not yet been completed.
- Final business-rule coverage has not yet been measured.

This list will be updated as each milestone is completed.

---

## 14. AI and Third-Party Usage

AI-assisted development and review tools used for this project include:

| Tool | Purpose |
|---|---|
| Claude | Assignment analysis, design planning, design review, and initial scaffold/documentation assistance |
| Google Antigravity | Comparison and review of project files |

The detailed AI prompt log is maintained in [`PROMPTS.md`](./PROMPTS.md).



### Third-party libraries

The project uses or plans to use libraries including FastAPI, Uvicorn, Pydantic, pytest, pytest-cov, httpx, Ruff, React, Vite, and TypeScript. SQLAlchemy and Alembic are planned for database integration.

---

## 15. Submission and Milestones

The project is organized into seven milestones, M0–M6, following the assignment requirements.

| Milestone | Focus | Status |
|---|---|---|
| M0 | Scaffold, health endpoint, frontend build, Docker Compose, documentation | In progress / verification |
| M1 | Database schema, migrations, and seed data | Planned |
| M2 | Domain rules and unit tests | Planned |
| M3 | API endpoints, validation, transactions, and concurrency | Planned |
| M4 | Expanded integration and concurrency tests | Planned |
| M5 | Deployment and deployment documentation | Planned |
| M6 | Final coverage report, review, and submission cleanup | Planned |

The final milestone scope and naming will follow the assignment's exact requirements.

See [`SUBMISSION.md`](./SUBMISSION.md) for the submission checklist.

---

## 16. License

This repository was created for the KJBN Labs Software Engineering Internship take-home assignment. No separate open-source license has been declared.