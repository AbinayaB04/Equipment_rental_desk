# SUBMISSION

## A. What I built

I built a full-stack Equipment Rental Desk using FastAPI, PostgreSQL, SQLAlchemy, and Alembic for the backend, with React, TypeScript, and Vite for the frontend. It supports member management, equipment inventory, reservations, checkout, returns, maintenance, payments, statements, and overdue-loan views. Business rules include 48-hour reservation expiry, seven-day loans, capped late fees, borrowing eligibility checks, and suspension controls. PostgreSQL transactions and row-level locks protect concurrent lending operations, while integer paise ensures exact monetary calculations.

Milestones M0–M6 implementation and documentation work are complete. The application is deployed with a Render backend, Neon PostgreSQL database, and Vercel frontend. Final release tagging is the remaining release step.

**Live application:** https://equipment-rental-desk-eight.vercel.app/

**Backend API:** https://equipment-rental-desk.onrender.com

**API documentation:** https://equipment-rental-desk.onrender.com/docs

**Source repository:** https://github.com/AbinayaB04/Equipment_rental_desk

## B. Three design decisions

### 1. Separate frontend and backend

**Alternative:** A server-rendered monolith.

**Reason:** React/TypeScript and FastAPI separate presentation from server-enforced rules and allow independent API testing.

**Trade-off:** Separate runtimes, CORS configuration, and environment settings add setup work.

### 2. PostgreSQL with row-level locking

**Alternative:** In-memory locks or optimistic version checks.

**Reason:** PostgreSQL transactions and `SELECT ... FOR UPDATE` serialize competing reservations and checkouts and preserve data integrity.

**Trade-off:** Concurrency tests need PostgreSQL, and transaction handling requires care.

### 3. Integer paise for money

**Alternative:** Binary floating-point values.

**Reason:** Integer paise avoids rounding errors in fees, payments, and balances.

**Trade-off:** Values need conversion for display in rupees and strict integer validation.

## C. The hardest part

The hardest part was preventing conflicting loan operations. Concurrent requests could try to reserve or check out the same item, so I used multithreaded tests with a barrier to reproduce the race. The service locks the item row inside a database transaction, allowing one valid transition while competing requests receive a conflict response.

A second challenge was reservation expiry. Expired reservations must not block new transactions, but read-only GET requests should not mutate the database. The application treats expired reservations as available in reads and reconciles them during relevant write operations.

I also hardened the reviewer-controlled test clock after extreme dates caused overflow errors. The API validates ISO-8601 timestamps, requires an authorized key, and limits clock offsets to ±90 days, returning structured errors for invalid values.

**Relevant commits:** `dfe8100` (business rules and concurrency), `4e69879` (REST API), `ddeb960` (input and clock hardening).

## D. How I handle failure

A central API handler returns consistent error codes, messages or details, and request IDs. Pydantic schemas validate inputs before database writes; service-layer domain errors explain invalid transitions and eligibility failures. Database conflicts become HTTP 409 responses without exposing driver details. Invalid reviewer-clock settings return HTTP 403 or 422. Lock contention can return HTTP 503 with `Retry-After`. Unexpected errors return a generic HTTP 500 response with a request ID, while details are logged server-side.

| Failure | Handling |
|---|---|
| Invalid input or numeric/date bounds | HTTP 422/400 with structured errors |
| Business-rule violation | Typed domain error mapped to HTTP 403/409 |
| Database constraint conflict | HTTP 409 without exposing database internals |
| Test clock disabled, unauthorized, or out of range | HTTP 403/422 |
| Lock contention | HTTP 503 with `Retry-After` |
| Unexpected exception | Generic HTTP 500 with request ID; details logged server-side |

## E. Milestone log

| Milestone | Status/date | Commit |
|---|---|---|
| M0 Scaffold | Complete, 2026-10-17 | `2f56c06` |
| M1 Domain model | Complete, 2026-10-17 | `e039207` |
| M2 Business rules | Complete, 2026-10-18 | `dfe8100` |
| M3 API | Complete, 2026-10-20 | `4e69879`, `ddeb960` |
| M4 UI | Complete and committed, 2026-10-21 | `f3b248b`, `5e1e6a7` |
| M5 Deployment | Deployed; backend startup migrations configured | `dfb56a7` |
| M6 Final verification and documentation | Documentation committed and pushed; release tag to verify | `7dec8cf` |

The documentation changes for M6 have been committed and pushed to `main`. The `v1.0` release tag must be confirmed or created and pushed before claiming the release is fully tagged.

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
| Error and exception handling | 5 | Typed domain errors and consistent error responses avoid leaking internal details. |
| Logging and observability | 4 | Request IDs, structured logs, and a health endpoint aid diagnosis. |
| Data modelling and persistence | 4 | PostgreSQL constraints, migrations, and seed data support reproducible setup. |
| API design | 5 | REST endpoints, OpenAPI docs, bounded pagination, and consistent status codes. |
| UI usability | 4 | Catalogue, member, payment, statement, and loan workflows are implemented and deployed. |
| Testing | 5 | Previously reported results: 264 backend tests passed with PostgreSQL and zero skipped, with 94% backend statement coverage; 26 frontend tests passed. These results were not rerun for the final documentation commit. |
| Deployment and operability | 4 | Frontend and backend are deployed separately, with Neon PostgreSQL and startup migrations configured. |
| Git hygiene | 4 | Milestone commits and `PROMPTS.md` track work; final release tagging remains to be verified. |
| Documentation and write-up | 4 | README and this submission document describe architecture, rules, tests, and deployment. |
