# SUBMISSION

## A. What I built

I built a full-stack Equipment Rental Desk using FastAPI, PostgreSQL, SQLAlchemy, and Alembic for the backend, and React, TypeScript, and Vite for the frontend. The application supports member management, equipment inventory, reservations, checkout, returns, maintenance, payments, statements, and overdue-loan views. Core rules include 48-hour reservation expiry, seven-day loans, capped late fees, borrowing eligibility checks, and suspension controls. PostgreSQL transactions and row-level locks protect concurrent lending operations, while integer paise keeps monetary calculations exact. Milestones M0–M3 are committed; M4 is implemented and verified locally, while cloud deployment and final release remain incomplete.

## B. Three design decisions

### 1. Separate frontend and backend
**Alternative:** A server-rendered monolith. **Reason:** React/TypeScript and FastAPI separate presentation from server-enforced rules and allow independent API testing. **Trade-off:** Separate runtimes, CORS configuration, and environment settings add setup work.

### 2. PostgreSQL with row-level locking
**Alternative:** In-memory locks or optimistic version checks. **Reason:** PostgreSQL transactions and `SELECT ... FOR UPDATE` serialize competing reservations and checkouts and preserve data integrity. **Trade-off:** Concurrency tests need PostgreSQL, and transaction handling requires care.

### 3. Integer paise for money
**Alternative:** Binary floating-point values. **Reason:** Integer paise avoids rounding errors in fees, payments, and balances. **Trade-off:** Values need conversion for display in rupees and strict integer validation.

## C. The hardest part

The hardest part was preventing conflicting loan operations. Concurrent requests could try to reserve or check out the same item, so I used multi-threaded tests with a barrier to reproduce the race. The service now locks the item row inside a database transaction, allowing one valid transition while competing requests receive a conflict response.

A second challenge was reservation expiry. Expired reservations must not block new transactions, but read-only GET requests should not mutate the database. The application treats expired reservations as available in reads and reconciles them during relevant write operations.

I also hardened the reviewer-controlled test clock after extreme dates caused overflow errors. The API validates ISO-8601 timestamps, requires an authorized key, and limits clock offsets to ±90 days, returning a structured validation error for invalid values.

**Relevant commits:** `dfe8100` (business rules/concurrency), `4e69879` (REST API), `ddeb960` (input and clock hardening).

## D. How I handle failure

Errors are returned through a central API handler with a stable error code, message/details, and request ID. Validation errors are caught by Pydantic schemas before database writes; service-layer domain errors explain invalid transitions and eligibility failures. Database integrity conflicts become HTTP 409 responses rather than exposing driver details. Invalid reviewer-clock settings return clear 403 or 422 responses. Lock contention can return HTTP 503 with `Retry-After`. Unexpected errors return a generic HTTP 500 response with a request ID; detailed exception information is logged server-side.

| Failure | Handling |
|---|---|
| Invalid input or numeric/date bounds | HTTP 422/400 with structured errors |
| Business-rule violation | Typed domain error mapped to HTTP 403/409 |
| Database constraint conflict | HTTP 409 without leaking database internals |
| Test clock disabled, unauthorized, or out of range | HTTP 403/422 |
| Lock contention | HTTP 503 with `Retry-After` |
| Unexpected exception | Generic HTTP 500 plus request ID; details logged server-side |

## E. Milestone log

| Milestone | Date/status | Commit hash |
|---|---|---|
| M0 Scaffold | 2026-10-17 | `2f56c06` |
| M1 Domain model | 2026-10-17 | `e039207` |
| M2 Business rules | 2026-10-18 | `dfe8100` |
| M3 API | 2026-10-20 | `4e69879`, `ddeb960` |
| M4 UI | Complete locally, 2026-10-21; commit pending | Pending |
| M5 Deployment | Not completed | — |
| M6 Documentation/tag | Not completed | — |

## F. If I had two more days

1. **Analytics dashboard:** Show equipment utilization, demand by category, and maintenance trends.
2. **Authentication and roles:** Add staff authentication and role-based permissions.
3. **Barcode/QR scanning:** Speed up equipment checkout and return.
4. **Reminders:** Notify members about reservation expiry and upcoming due dates.
5. **Condition history:** Store inspection photos and item-condition records at checkout and return.

## G. Self-assessment (1 to 5)

| Criterion | Score | Justification |
|---|---:|---|
| Business logic correctness | 5 | Rules cover expiry, loan duration, fee caps, eligibility, active-loan limits, and suspension. |
| Code clarity and structure | 4 | Services, routers, schemas, and database models are separated. |
| Error and exception handling | 5 | Typed domain errors and a consistent error response prevent internal details leaking. |
| Logging and observability | 4 | Request IDs, structured logs, and a health endpoint aid diagnosis. |
| Data modelling and persistence | 4 | PostgreSQL constraints, migrations, and seed data support reproducible setup. |
| API design | 5 | REST endpoints, OpenAPI docs, bounded pagination, and consistent status codes. |
| UI usability | 3 | Catalogue, member, payment, statement, and loan workflows are implemented and locally verified; M4 commit remains pending. |
| Testing | 5 | 264 backend tests passed with PostgreSQL, 0 skipped; backend statement coverage is 94%. The frontend has 26 passing tests. |
| Deployment and operability | 2 | Docker Compose works locally; cloud deployment is not complete. |
| Git hygiene | 4 | Milestone commits and `PROMPTS.md` track work; final tag remains pending. |
| Documentation and write-up | 4 | README and this submission document architecture, rules, tests, and current status. |
