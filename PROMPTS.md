# Prompt Log

Every prompt I typed as a request to an AI assistant, in order, with the tool used. “Answer” is a one-line factual summary of what the tool returned. “What I did” records how I used the response.

---

## Entry 1

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** Pasted the two assignment documents (common instructions + Problem 1) For analysis and got an idea.
- **Answer:** Orientation summary of deliverables, rubric, and important requirements in Problem 1.
- **What I did:** Reviewed the assignment requirements and used the summary to organize the implementation work.

## Entry 2

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** "is there any requirement to keep the repo name?"
- **Answer:** Explained that no specific repository name was required and that the README must identify the selected problem.
- **What I did:** Kept the existing GitHub repository name after confirming that the assignment did not mandate a specific name.

## Entry 3

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** "https://github.com/AbinayaB04/Equipment_rental_desk.git this is the repo i created, so explain me the problem statement. line by line, what are their expectations like that"
- **Answer:** Provided a section-by-section explanation of Problem 1, including requirements, rules, and edge cases.
- **What I did:** Used the explanation to understand the problem statement, expected functionality, and edge cases.

## Entry 4

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** "How to proceed with, they are asking many things right, mainly README must be perfect along with the commits in git, milestone completion and mainly AI chat logs, how do these?"
- **Answer:** Explained how to organize project documentation, AI prompt logs, Git commits, and milestone work.
- **What I did:** Used the workflow guidance to organize the README, milestone commits, and AI prompt log.

## Entry 5

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** "yes" — accepting the offer to generate README, PROMPTS.md, and other skeleton files.
- **Answer:** Generated initial project documentation and configuration skeletons.
- **What I did:** Used the generated skeleton files as the starting point for the M0 scaffold.

## Entry 6

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** "okayy for front end we can do react, backend python, flask or fast api which is prefered by them, and for DB postgresql can be cloud so that will be easy to deployment."
- **Answer:** Recommended FastAPI, PostgreSQL, and React with TypeScript, along with a suggested folder structure.
- **What I did:** Chose FastAPI, React with TypeScript, and PostgreSQL for the project stack.

## Entry 7

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** "can i also use antigravity ?"
- **Answer:** Explained how Antigravity could be used alongside other AI tools and the importance of documenting its use.
- **What I did:** Considered Antigravity as an additional development and file-review tool.

## Entry 8

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** "based on this can i get the updated readme"
- **Answer:** Generated an updated README skeleton based on the selected technology stack.
- **What I did:** Used the updated README as a starting point and adapted the project configuration to the local setup.


## Entry 9

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** Request for the full implementation plan without application code. Full prompt below.
- **Answer:** Provided an implementation plan covering the repository structure, database schema, API, layers, business rules, tests, concurrency, test clock, milestones, and deployment.
- **What I did:** Used the implementation plan to organize the architecture, API design, business rules, tests, and milestone sequence.

<details>
<summary>Full prompt text (Entry 9)</summary>

I am building the KJBN Labs Software Engineering Internship take-home assignment, Problem 1: Equipment Rental Desk. I will provide the complete assignment specification.

Tech stack:

- Backend: Python, FastAPI
- Frontend: React, TypeScript, Vite
- Database: PostgreSQL
- Testing: pytest, pytest-cov, and API-level tests
- Local deployment: Docker and Docker Compose
- Git: GitHub with milestone-based Conventional Commits

Your task in this first response is ONLY to design the implementation plan. Do not generate application code yet.

Please provide:

1. A clean monorepo folder structure.
2. The database entities, columns, relationships, constraints, and indexes.
3. The API endpoint list with HTTP methods, request/response shapes, and error status codes.
4. A clear separation between API routes, business services, database access, and domain exceptions.
5. A numbered list of every business rule and its corresponding unit tests.
6. Boundary tests for reservation expiry, the ₹100 balance threshold, the three-active-loan limit, the ₹200 late-fee cap, replacement-value cap, and payment overbalance.
7. A concurrency-safe design for two simultaneous check-out requests and other conflicting state changes.
8. A reviewer-controlled test clock that cannot accidentally be enabled or abused in production.
9. The seven required milestones M0–M6, with the files and tests expected at each milestone.
10. A deployment plan, environment variables, Docker configuration, seed data, CI, coverage report, README, SUBMISSION.md, and PROMPTS.md.

Follow the assignment exactly. Do not invent requirements or omit edge cases. Clearly identify ambiguous rules and propose assumptions for my review.

Prioritize correctness, readable code, and a complete Core implementation over Stretch features. Explain any important design trade-offs in simple language because I must be able to defend the implementation during an interview.

After presenting the plan, wait for my approval before generating code.

</details>

## Entry 10

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** Request to review and revise the implementation plan on seven issues: maintenance and loan consistency, reservation expiry, payment concurrency, late-fee assumptions, test clock, transactional integrity, and assignment compliance. Full prompt below.
- **Answer:** Returned revised plan sections, a list of changes, and remaining decisions.
- **What I did:** Used the review to refine the plan's concurrency handling, reservation expiry, maintenance behavior, late-fee assumption, test clock, and transactional rules.

<details>
<summary>Full prompt text (Entry 10)</summary>

Your implementation plan looks good overall. Before I approve it, please review and resolve the following issues.

1. ITEM AND LOAN STATE CONSISTENCY

The item can enter maintenance from any state, including Reserved and Checked Out. Design the state model so that an item in maintenance can still have an outstanding checked-out loan. Explain how returning the item, restoring it to Available, and calculating overdue status will work. Do not lose loan history or allow a second active loan.

2. RESERVATION EXPIRY

Ensure expired reservations are handled correctly on both reads and writes. A read must show the correct effective status without requiring a cron job. A subsequent reservation must safely expire the old reservation inside a transaction. Handle concurrent requests and ensure the partial unique index cannot leave an item permanently unavailable.

3. PAYMENT AND BALANCE CONCURRENCY

Review the locking strategy for payment, return, and member balance calculations. Two simultaneous payments must not both spend the same outstanding balance. A return must record its fee exactly once. Explain which rows each operation locks and in what order.

4. LATE-FEE ASSUMPTION

Keep the proposed 24-hour rounding calculation only as an explicit documented assumption. Add tests for one second late, exactly 24 hours late, and 24 hours plus one second late. Explain why this interpretation was chosen.

5. TEST CLOCK

Ensure the test clock is disabled by default, is authorized when enabled in production, is request-scoped, and is tested. Explain how reviewers can use it without accidentally corrupting the demo data.

6. TRANSACTIONAL INTEGRITY

Review all state-changing operations for rollback behavior, consistent locking, database constraints, and correct HTTP errors. In particular, ensure that a failed checkout, return, payment, cancellation, or maintenance transition cannot leave the item and loan in inconsistent states.

7. ASSIGNMENT COMPLIANCE

Check the revised plan against every Core requirement and every listed edge case in the assignment. Identify any missing requirements, contradictions, or assumptions that need to be documented.

Return only the revised sections, a short list of changes, and any remaining decisions that need my approval. Do not generate application code yet.

After I approve the revised plan, we will implement one milestone at a time, starting with M0. Keep a record of this prompt in PROMPTS.md along with the actual prompts used throughout development. Do not invent commit hashes, test results, coverage figures, or deployment results.

</details>

## Entry 11

- **Tool:** Claude (claude.ai)
- **Date:** 2026-10-17
- **Prompt:** Approval of the revised plan with nine decisions, requests for final clarifications about expired reservations, effective item status, the unique index, and the monotonic clock guard, followed by an M0-only scaffold request. Full prompt below.
- **Answer:** Clarified the plan and supplied an M0 scaffold ZIP with PowerShell instructions for running and verifying it.
- **What I did:** Used the scaffold as the starting point for M0, reviewed the configuration, and ran the local quality checks and Docker Compose setup.

<details>
<summary>Full prompt text (Entry 11)</summary>

I approve the revised plan with the following decisions:

1. Use the orthogonal maintenance flag and derive item status from the flag and loan records.
2. Allow an item to enter maintenance while checked out. Keep the loan open, allow its return, and keep the item in maintenance until staff restore it.
3. Cancel a live reservation when its item enters maintenance, recording `cancel_reason = item_maintenance`.
4. Reject payments exceeding the outstanding balance with HTTP 422. Do not create credit balances.
5. Keep loan-ID routes for checkout, return, and cancellation.
6. Keep the test clock disabled by default and require authorization when enabled in production.
7. Keep the per-item monotonic clock guard. Apply it to history-changing operations, not read-only requests, and document its behavior clearly.
8. Keep the proposed elapsed-24-hour late-fee calculation as an explicit assumption, with the boundary tests and README explanation.
9. Use HTTP 503 `BUSY` with `Retry-After` for lock timeouts.

Before starting M0, please resolve these final details in the plan:

- Ensure every relevant write operation handles expired reservations consistently. In particular, restoring an item must not fail because an expired reservation still has stored status `reserved`. GET requests must remain read-only.
- Ensure effective item status, active-loan counts, and the partial unique index work together correctly when an expired reservation has not yet been cleaned up.
- Define precisely which loan/item events the monotonic clock guard compares, and make sure normal read-only requests are not blocked by it.
- Keep all assignment requirements and edge cases covered by tests and documentation.

Update the plan with these clarifications, then begin M0 only. Do not implement M1 or later milestones yet.

For M0, deliver the minimal working scaffold, FastAPI health endpoint and test, React/TypeScript frontend that builds, Docker Compose configuration, `.env.example`, `.gitignore`, Ruff/test configuration, and the required README, SUBMISSION.md, and PROMPTS.md skeletons.

Record the actual prompts in PROMPTS.md and leave each "What I did" field for me to complete. Do not invent test results, coverage, commit hashes, or deployment status.

After implementing M0, tell me the exact commands to run on Windows PowerShell, the expected results, and how to verify each requirement. Do not proceed until I have run and checked M0.

</details>

## Entry 12

- **Tool:** Antigravity
- **Date:** 2026-10-17
- **Prompt:** Reviewed and compared the current project folder with the extracted M0 ZIP to identify differences.
- **Answer:** Reported that the code files were identical, while the README and Docker Compose configuration differed.
- **What I did:** Used the comparison to retain the current project configuration and avoid overwriting the working port mappings.

---

<!-- Template for future entries

## Entry N

- **Tool:** Name of AI tool
- **Date:** YYYY-MM-DD
- **Prompt:** Actual prompt or a truthful concise description of the request.
- **Answer:** One-line factual summary of the response.
- **What I did:** Briefly describe what I actually used, edited, or rejected.

-->