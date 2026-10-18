# SUBMISSION

## A. What I built

I created the initial Equipment Rental Desk project scaffold using FastAPI, React with TypeScript, PostgreSQL, and Docker Compose. I configured the backend development environment, frontend build, container setup, and basic health endpoint. The backend linting and formatting checks pass, all 6 current backend tests pass, and the frontend production build succeeds. Docker Compose starts the backend, database, and frontend containers successfully. The core rental workflow—including reservations, checkouts, returns, payments, and business-rule enforcement—has not yet been implemented.

## B. Three design decisions

### 1. Decision: Separate the frontend and backend

**Alternative considered:** Build the application as a single full-stack service.

**Why I chose this:** A React and TypeScript frontend with a FastAPI backend separates the user interface from business logic. This makes the API easier to test independently and allows the frontend and backend to evolve separately.

**What it cost me:** The project needs separate build and development configurations, API URL configuration, and cross-origin settings.

### 2. Decision: Use PostgreSQL as the database

**Alternative considered:** Use an in-memory data store or SQLite during development.

**Why I chose this:** PostgreSQL is suitable for a rental system that will need persistent records, relationships, transactions, and database-level integrity constraints. It also provides a suitable foundation for implementing concurrent reservation and checkout operations.

**What it cost me:** The project requires database configuration and a running database service. Schema migrations and persistence logic still need to be implemented in later milestones.

### 3. Decision: Use Docker Compose for local development

**Alternative considered:** Run the frontend, backend, and database manually as separate processes.

**Why I chose this:** Docker Compose provides a repeatable way to start the application services and makes it easier to verify that the components work together in a consistent environment.

**What it cost me:** Container configuration, port mapping, health checks, and environment variables introduce additional setup and debugging work.

## C. The hardest part

At the current milestone, the main challenge was establishing a consistent development environment across the frontend, backend, and database. The application uses different tools for Python dependencies, frontend packages, code quality checks, and container orchestration. I verified the backend using pytest and Ruff, checked the frontend with a production build, validated the Compose configuration, and started the services together. These checks helped distinguish configuration or build problems from application-level failures. The initial scaffold exposes a health endpoint, but it does not yet implement the rental domain or its business rules. Therefore, I cannot honestly claim to have completed or debugged the hardest business-logic problem at this stage. I will update this section after implementing the rental workflow, explaining the specific issue encountered, how I reproduced it, the fix, and the relevant commit hashes.

**Relevant commit hashes:** To be added after verifying the commits for this milestone.

## D. How I handle failure

The current implementation is a scaffold, so error handling for the complete rental workflow is not yet implemented.

| Failure type | Current status and intended handling |
|---|---|
| Bad request | FastAPI/Pydantic will validate request data and return an appropriate 4xx response. |
| Business-rule violation | Domain or service logic will reject invalid operations with a clear client-facing error. |
| Database error | Database operations will use appropriate transaction handling; expected conflicts will be mapped to suitable API responses. |
| Unexpected exception | A centralized handler will return a generic error without exposing internal details. Server-side logs will capture diagnostic information. |

These are implementation plans, not claims that all handlers already exist. Before submission, I will update this section to describe the actual exception-handling and logging behavior.

## E. Milestone log

| Milestone | Date completed | Commit hash |
|---|---|---|
| M0 Scaffold | 2026-10-17 | 2f56c06 |
| M1 Domain model | 2026-10-17 | e039207 |
| M2 Business rules | 2026-10-18 | dfe8100 |
| M3 API | Ready for commit | Pending commit |
| M4 UI | Not completed | — |
| M5 Deployment | Not completed | — |
| M6 Documentation (v1.0) | Not completed | — |

## F. If I had two more days

1. Implement and test the rental domain model and database migrations.
2. Complete reservation, checkout, return, payment, and maintenance workflows.
3. Add validation, transaction safety, concurrency handling, and consistent API error responses.
4. Expand automated tests to cover business rules, boundary cases, and failure scenarios.
5. Complete the UI, verify the full application through Docker Compose, and update the documentation and deployment instructions.

## G. Self-assessment (1 to 5)

Scores below are provisional and reflect the current scaffold, not a completed rental application.

| Criterion | Score | Justification |
|---|---:|---|
| Business logic correctness | 1 | Rental business rules are not implemented yet. |
| Code clarity and structure | 4 | The project separates frontend, backend, and configuration. |
| Error and exception handling | 2 | Framework-level validation exists, but application-specific handling remains incomplete. |
| Logging and observability | 2 | Basic service health checks are configured; business-level logging is still pending. |
| Data modelling and persistence | 1 | PostgreSQL is configured, but the rental schema and persistence layer are not complete. |
| API design | 2 | The initial health endpoint exists; rental endpoints are pending. |
| UI usability | 1 | The full rental interface has not been implemented. |
| Testing | 3 | The current backend suite has 6 passing tests; business-rule coverage is pending. |
| Deployment and operability | 3 | The local Docker Compose stack starts successfully; production deployment is pending. |
| Git hygiene | 3 | The repository is initialized; milestone commits and final history still need to be completed and verified. |
| Documentation and write-up | 3 | Initial setup and project documentation are being prepared; final documentation depends on implementation. |
