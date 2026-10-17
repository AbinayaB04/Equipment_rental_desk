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

## Entry 13

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** "Explain what this problem is and help me fix it: Expected omitted end tag <meta> instead of self-closing element <meta/> @[d:\files\KJBN\Equipment_rental_desk\frontend\index.html:L4]"
- **Answer:** Explained HTML5 void element rules and updated `frontend/index.html` to remove the XML-style self-closing slash from `<meta>` tags.
- **What I did:** Used as-is to fix the HTML linter error and verified the frontend build succeeded.

## Entry 14

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** "remove unnecessary stuffs in the env.example"
- **Answer:** Removed verbose meta-commentary, milestone disclaimers, and unused future variables from `.env.example`.
- **What I did:** Used as-is to clean up the environment template into standard `# Backend`, `# Frontend`, and `# Database` sections.

## Entry 15

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Request to analyze the assignment specification and Problem 1: Equipment Rental Desk requirements. Full prompt below.
- **Answer:** Provided a comprehensive domain analysis covering entities, the 7 business rules, reviewer edge cases, non-negotiables, scoring rubric, and milestone progression.
- **What I did:** Used as-is to align on requirements before starting Milestone 1 planning.

<details>
<summary>Full prompt text (Entry 15)</summary>

firstly analyse this content
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 1
Software Engineering Internship
Take-Home Coding Assignment
KJBN Labs · Version 1.0 · October 2026
In one sentence: take the problem you were sent (see Section 4), build a small but complete product
(backend API + web/mobile UI + database), host it on a free tier, commit your progress in logical
milestones, and submit a repository link, a live link, a README and a short write-up in the format given
in Section 7.
1. Purpose of this assignment
We are not looking for the most features or the fanciest UI. We are looking for evidence that you can
take a small business problem, model it correctly, implement its rules so they hold up under bad
input, and explain your decisions clearly. Every problem below is deliberately small in domain but
has enough business logic that shortcuts will show. A boring, correct, well-structured solution beats
an ambitious, broken one.
What we are trying to learn about you:
• Can you translate written business rules into code and tests, including the edge cases nobody
spelled out?
• Do you structure a codebase so another engineer can find things, and do you name things
honestly?
• Do you handle failure deliberately — validation, exceptions, logs — or hope it never happens?
• Do you work in increments, commit meaningfully, and document as you go?
• Can you write about your own work in a precise, honest way?
2. Deliverables
# Deliverable Details
D1 Backend API A JSON HTTP API implementing all business rules of the chosen problem. Rules must
live in the backend, not only in the UI.
D2 Database Persistent storage with a schema or migrations in the repo. SQLite is acceptable;
PostgreSQL is a plus. Include a seed script that loads realistic sample data.
D3 User interface A web UI (TypeScript) or Flutter app covering the core flows listed in the problem. It
must call your API — no mocked data in the final build.
D4 Hosted
deployment
Backend and UI reachable on public URLs, with seed data already loaded, for the
whole review period. Free tiers that sleep and cold-start are fine — say so in the
README.
D5 Deployment
scripts
Everything needed to deploy from a clean clone, committed to the repo: a
Dockerfile per service (or an equivalent build spec), a docker-compose.yml or
single script that brings up backend + database + UI locally, the hosting provider's
config file (render.yaml, fly.toml, vercel.json, etc.) and a migrate-and-seed
script. A CI workflow that runs tests on push is strongly recommended. Manual steps
done in a provider dashboard must be listed in the README.
D6 Git repository A public GitHub/GitLab repository with a milestone-based commit history (Section
5). Monorepo or two repos — your choice; link both if two.
D7 README.md In the exact structure given in Section 6.
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 2
# Deliverable Details
D8 SUBMISSION.md Your write-up in the exact structure given in Section 7. Maximum two pages
equivalent.
D9 Unit tests +
coverage report
Automated unit tests for every business rule, plus API-level tests. One command
runs the tests; one command (or the same one) produces a code coverage report
for the backend. Commit the coverage summary (e.g. coverage.txt or the HTML
index) and state the percentage in the README. Target ≥ 80% on the business-rules
layer; overall percentage is reported, not graded.
D10 PROMPTS.md A log of every prompt you gave to any AI assistant while building this (Section 9).
Either a PROMPTS.md file in the repo root or a section at the end of the README.
3. Technology choices
Use a language you are productive in. We recommend the stacks below because they are what we
use and review most fluently; other choices are allowed if you justify them in the README. Do not
use a low-code builder, a CRUD generator, or a scaffolding tool that writes the business logic for you.
Layer Recommended Notes
Backend Python (FastAPI, Django, Flask) · Go
(net/http, chi, Gin, Echo) · TypeScript (Node
with Express, Fastify, NestJS, Hono)
Any framework is fine. Expose
OpenAPI/Swagger docs if your framework
makes it easy — it helps us review.
Frontend TypeScript (React, Vue, Svelte, Angular,
SolidJS) · Flutter (web build or Android APK +
web)
Plain, readable UI is enough. If you use Flutter,
deploy the web build and optionally attach an
APK.
Database SQLite (file) · PostgreSQL (Neon, Supabase,
Render free tier) · Turso/libSQL
Keep schema and migrations in the repo. Free
Postgres tiers may pause after inactivity;
document how to re-seed.
Backend
hosting
Render, Fly.io, Koyeb, Google Cloud Run,
Railway (trial), Deta Space, PythonAnywhere
(Python only)
Free-tier terms change often — check them
before you start. Containerising with a
Dockerfile makes most of these trivial.
Frontend
hosting
Vercel, Netlify, Cloudflare Pages, GitHub
Pages, Firebase Hosting
Configure CORS on the API for your UI origin.
Put the API base URL in an environment
variable, not in code.
Non-negotiables regardless of stack: configuration via environment variables with a committed
.env.example; no secrets in git history; one command to run the backend, one to run the UI, one to run
tests; all money values in paise/integer or decimal types — never binary floats; all timestamps stored in
UTC and displayed in IST (Asia/Kolkata).
4. Your problem
You will receive one problem statement as a separate PDF (Problem 1 to Problem 5). Each problem
is a different kind of engineering challenge, calibrated to similar effort. Build only the problem you
were sent; do not combine or substitute. Every problem statement has Core requirements
(mandatory) and Stretch ideas (optional; attempt them only after Core is complete and tested),
plus the exact edge cases reviewers will try.
Where a rule is ambiguous, make a sensible decision and record it under Assumptions in your
README — we grade the reasoning, not whether you guessed our intent. If your problem involves
time-based rules (due dates, expiry, cancellation windows), it will ask you to provide a reviewer
clock override (e.g. an X-Test-Clock header or admin setting) so the logic can be tested without
waiting days. Document it in README section 10.
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 3
5. Git workflow and commit guidelines
Your commit history is part of the submission and is reviewed as carefully as the code. We will run
git log --oneline --graph and read the diff of several commits. A single "initial commit" with the
whole project, or a history of "fix", "wip", "final final" messages, is an automatic deduction.
5.1 Milestones
Work through the milestones below in order. Each milestone must end with at least one commit
whose message names the milestone ([M2]) and leaves the repository in a runnable state. Within a
milestone, commit as often as makes sense — one logical change per commit.
Milestone What is done when it is complete
M0 — Scaffold Repo created, folder structure, linters/formatters configured, .env.example, README
skeleton with the chosen problem.
M1 — Domain model Entities and schema/migrations; seed script; the key business rules written down as test
cases (failing is fine).
M2 — Business rules Core rules implemented as pure, testable code (services/use-cases) with passing tests. No
HTTP yet is acceptable.
M3 — API Endpoints wired to the rules; validation; error responses; request logging; OpenAPI if
available.
M4 — UI Core flows working against the local API.
M5 — Deployment Dockerfiles, compose file, provider config and migrate-and-seed script committed;
backend and UI live; seed data loaded; CORS; health endpoint; CI running tests.
M6 —
Documentation
README complete; SUBMISSION.md written; final tag v1.0.
5.2 Commit message format
Use Conventional Commits with the milestone tag in the subject. Subject ≤ 72 characters,
imperative mood. The body (optional but encouraged for non-trivial commits) explains why, not
what — the diff already shows what.
feat(loans): [M2] enforce 3-active-loan limit per member
Reserved, checked-out and overdue loans all count as active. Chose to
check in the service layer rather than a DB constraint because the
definition of "active" depends on the clock (overdue is derived).
fix(api): [M3] return 409 instead of 500 on double check-out
test(payout): [M2] cover advance recovery cap at 30% of gross
chore: [M0] add ruff and pre-commit config
docs: [M6] add architecture section and assumptions to README
Allowed types: feat, fix, test, refactor, docs, chore, ci, perf. Scope is the module or
feature touched.
5.3 Rules
• Commit from day one; do not build locally for a week and then push once. Timestamps are visible
and we look at them.
• Never commit secrets, node_modules, build output, or database files with real-looking data. If you
accidentally do, rewrite history and rotate the secret.
• Do not squash the history before submitting. We want to see the path, including dead ends you
backed out of (a revert commit with a reason is a positive signal).
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 4
• Branches and pull requests are optional for a solo project; if you use them, keep merge commits
meaningful.
• Tag the final submission v1.0. Commits after the deadline are ignored.
6. README.md — required structure
Use these headings in this order. A reviewer who has never seen your project should be running it
locally within five minutes using only the README. Keep it factual; marketing language is a negative
signal.
Section Must contain
1. Title and one-liner Project name, your problem number and name, one sentence on what it does.
2. Live links UI URL, API base URL, API docs URL (if any), test credentials if you added auth. Note
cold-start delay if applicable.
3. Tech stack Language, framework, database, hosting for each layer, and one line on why for any
non-recommended choice.
4. Architecture A diagram (image or ASCII) of the components and request flow; folder structure with
a sentence per top-level folder; where the business rules live and why there.
5. Running locally Prerequisites with versions; .env variables explained; exact commands to install,
migrate, seed, run backend, run UI (and the one-command compose equivalent).
Must work on a clean machine.
5a. Deployment How the hosted instance was deployed, step by step, pointing at the scripts and
config files in the repo; which steps were manual in a provider dashboard; how to
redeploy after a code change; how to re-seed.
6. Running tests and
coverage
The test command; the coverage command; the coverage percentage for the
backend overall and for the business-rules module(s); what is covered; what is
deliberately not covered and why.
7. API overview A table of endpoints: method, path, purpose, main error codes. Link to OpenAPI if
present.
8. Business rules and
assumptions
Each rule from the problem, mapped to where it is enforced (file/function) and its
test. Every ambiguity you resolved, as a numbered assumption.
9. Error handling and
logging
Your error-response shape; how validation vs. domain vs. unexpected errors are
distinguished; what is logged, at which level, with what correlation id; where logs can
be seen on the hosted instance.
10. Reviewer aids How to set the test clock; how to re-seed; sample files; anything that makes our
review faster.
11. Known limitations What does not work or was skipped, stated plainly. This section being honest earns
points; it being empty costs them.
12. AI and third-party
usage
Which AI assistants, templates or snippets you used and for what, and a link to your
prompt log (PROMPTS.md, or the log itself as section 13). Allowed — but undisclosed
use is disqualifying (Section 9).
7. SUBMISSION.md — your write-up (max 2 pages)
This is where you describe what you have done. It is separate from the README because its
audience is different: the README is for someone running the code; this is for someone judging your
engineering judgement. Use these headings exactly, in this order, and respect the length limits.
Section Content Limit
A. What I built Plain-language summary of the product, which Core features are
complete, which are partial.
5 sentences
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 5
Section Content Limit
B. Three design
decisions
For each: Decision · Alternative considered · Why I chose this ·
What it cost me. Choose decisions where a reasonable engineer could
disagree (e.g. derived vs. cached balances, where validation lives,
transaction strategy).
3 × ~80 words
C. The hardest part The specific problem that took longest or that you got wrong first; how
you found out; what you changed. Reference the commit hashes.
150 words
D. How I handle
failure
How a bad request, a rule violation, a database error and an unexpected
exception each travel from where they occur to what the user sees and
what gets logged. One short paragraph or a small table.
150 words
E. Milestone log Table: milestone · date completed · commit hash. 7 rows
F. If I had two more
days
Ordered list of what you would do next and why that order. 5 items
G. Self-assessment Score yourself 1–5 on each rubric criterion in Section 8 with one
justification each. We compare this with our scores; calibration is itself a
signal.
11 rows
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 6
8. How you will be evaluated
Two engineers review every submission independently, then reconcile. Scores are out of 100 using
the weights below. Shortlisted candidates get a 45-minute call where you walk us through your code
and we ask you to extend it live with one small rule change — so understand every line you submit.
8.1 What we actually do
1 Open the live UI and use it as an end user for 15 minutes, deliberately trying the edge cases
listed under your problem.
2 Hit the API directly with malformed input, missing fields, wrong types, out-of-range values and
concurrent requests, and watch the responses and the logs.
3 Clone the repo, follow the README on a clean machine, run the tests.
4 Read the code top-down: entry point → routing → business rules → persistence. Then read the
tests.
5 Read the git log and open four or five commits chosen at random plus the milestone commits.
6 Read SUBMISSION.md and compare your self-assessment with ours.
8.2 Rubric
Criterion Wt. Excellent (full marks) looks like Needs work looks like
Business logic
correctness
25 Every Core rule enforced in the backend;
listed edge cases handled; money and
time handled precisely; concurrency cases
addressed and explained.
Rules only in the UI; off-by-one on
dates or boundaries; float money;
concurrent requests corrupt state.
Code clarity and
structure
14 Clear layering (API / rules / persistence);
small functions with honest names; no
dead code; consistent style enforced by a
linter; a newcomer can find any rule in
under a minute.
Business rules inside route handlers
or UI components; 300-line functions;
copy-pasted blocks; misleading
names.
Error and
exception handling
10 Validation, domain and unexpected errors
are distinct types mapped to consistent
HTTP codes and one response shape; no
stack traces to clients; failures leave data
consistent (transactions); the UI shows
actionable messages.
Everything is 500 or 200; bare
except: pass; partial writes on
failure; alerts with raw JSON.
Logging and
observability
8 Structured logs with level, timestamp,
request/correlation id, and the domain
identifiers involved; rule violations logged
at warn with context; a health endpoint;
logs viewable on the hosted instance.
print debugging left in; secrets or PII
in logs; nothing logged on errors; log
noise on every request body.
Data modelling
and persistence
9 Schema matches the domain; constraints
and indexes where rules need them;
migrations in repo; seed data realistic;
derived vs. stored data chosen
deliberately and documented.
Everything nullable; JSON blobs for
relations; no constraints; schema
created by hand on the server.
API design 8 Resource-oriented, predictable paths;
correct verbs and status codes;
pagination/filtering where lists can grow;
OpenAPI or equivalent; versioned or at
least stable shapes.
One /doThing endpoint; GET with
side effects; inconsistent naming;
unbounded lists.
UI usability 6 Core flows completable without
instructions; invalid actions disabled or
explained; loading and error states shown;
works at laptop and phone widths.
Blank screens on error; actions
available in impossible states;
hard-coded API URL; only works at
one window size.
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 7
Criterion Wt. Excellent (full marks) looks like Needs work looks like
Testing 7 Business rules covered by fast unit tests
with clear names; API-level tests; a
boundary test for every numeric rule; one
command runs everything; coverage
report committed and ≥ 80% on the rules
layer with uncovered areas explained.
Only a hello-world test; tests that hit
the live server; tests that pass
regardless of logic; no coverage
report, or high coverage from tests
without assertions.
Deployment and
operability
5 Clean clone deploys with the committed
scripts and documented steps;
one-command local bring-up;
migrate-and-seed script; health endpoint;
CI runs tests; CORS and env config
handled; secrets never in repo;
parameterised queries and basic input
sanitisation throughout.
Deployed by hand with no record of
how; local setup needs
undocumented steps; database
created manually on the server;
string-built SQL; secrets or debug
endpoints exposed on the hosted
instance.
Git hygiene 4 Milestone commits present; messages
follow Section 5; history shows steady
progress; no secrets or junk committed;
tagged v1.0.
One giant commit; vague messages;
secrets in history; build artefacts
committed.
Documentation
and write-up
4 README runs on a clean machine first
time; assumptions listed; limitations
honest; SUBMISSION.md follows the
format, is specific, cites commits, and
self-assessment matches reality.
README is the framework default;
write-up is generic or exceeds limits;
limitations section empty while bugs
are obvious.
8.3 Automatic deductions and disqualifiers
• No working hosted link at review time: −20. (Tell us in advance if a free tier was shut down; we
can re-check once.)
• No deployment scripts in the repo (deployment reproducible only from memory): −5.
• Business rules enforced only in the frontend: −15.
• Single-commit or uncommitted-until-the-last-day history: −10.
• No coverage report, or no prompt log while AI usage is declared: −5 each.
• Application crashes (5xx) on any malformed input we try: −5 per distinct crash, up to −15.
• Secrets committed to the repository: −10 and we will tell you to rotate them.
• Disqualifying: plagiarised code presented as your own; undisclosed AI-generated code you
cannot explain on the call; submitting a different problem than the one declared in the README.
8.4 What does not matter
Visual design beyond basic clarity; number of stretch features; choice between recommended
stacks; using an ORM vs. raw SQL; monorepo vs. two repos; whether you added authentication
(optional; if you do, keep it simple and give us credentials).
9. Rules, AI usage and getting help
• Timeline: you have 7 calendar days from the email that delivered this document. Reply to that
email with your links. Late submissions are reviewed only if you wrote to us before the deadline
with a reason.
• AI assistants (Copilot, ChatGPT, Claude, Cursor, etc.) are allowed. You must disclose what
you used and for what in README section 12, and you must keep a prompt log: every prompt
you sent, in order, with the tool name and a one-line note on what you did with the answer (used
as-is / edited / rejected). Put it in PROMPTS.md at the repo root or as the last section of the
README. Chat-style autocomplete does not need logging; anything you typed as a request does.
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 8
We read the log — a thoughtful log is a positive signal, an empty one next to obviously generated
code is disqualifying. You must be able to explain and modify every line on the call. We suggest
using AI for boilerplate and asking it questions, and writing the business rules yourself — that is
the part we are hiring for.
• Copying an existing project or another candidate's work is disqualifying. Using libraries is not
copying.
• Questions: email us at any point. We answer clarification questions within one working day and
share the answer with all candidates on the same problem. Decisions you make yourself and
document as assumptions are never marked wrong.
• Scope discipline: a complete Core with zero Stretch beats a half-done Core with three Stretch
items every time.
• Data: use invented names and phone numbers in seed data. Do not use real people.
10. Submission checklist
Reply to the assignment email with the items below. Check each one before sending.
Item
☐ Repository URL (public) — tagged v1.0
☐ Live UI URL and live API URL (plus docs URL if any), with test credentials if you added auth
☐ README.md follows Section 6; a clean clone runs with the documented commands
☐ SUBMISSION.md follows Section 7 and is within limits; milestone table has real commit hashes
☐ Unit tests pass with one command; coverage report generated, committed, and percentage stated in the
README
☐ Seed data is loaded on the hosted instance; the reviewer clock override (if your problem requires one) is
documented
☐ No secrets, build output or dependencies in git; .env.example present
☐ You have personally tried every edge case listed under your problem against the hosted version
☐ AI and third-party usage disclosed; PROMPTS.md (or README prompt-log section) contains every prompt
used
☐ Your name, phone and the problem number are in the email body
Build something you would be happy to defend line by line. — Engineering, KJBN Labs
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 1
Software Engineering Internship · Take-Home Assignment
Problem 1: Equipment Rental Desk
KJBN Labs · Version 1.0 · October 2026 · Read together with the Common
Instructions and Evaluation Criteria PDF
Before you start: the common PDF defines the deliverables (API + UI + database + hosting + unit
tests with coverage report + prompt log), the recommended stacks, the milestone commit rules, the
README and SUBMISSION.md formats, and the rubric. This PDF contains only the problem. Build the
Core requirements fully and test them before touching any Stretch item. Every business rule below must
be enforced in the backend. Record every ambiguity you resolve as a numbered assumption in your
README.
PROBLEM 1
Equipment Rental Desk
Type: Workflow / state machine · Domain: Community tool library
Context. A neighbourhood tool library lends equipment (drills, ladders, tillers, projectors) to
registered members. Today it runs on a notebook; the volunteer desk wants a system that prevents
the mistakes they keep making: lending an item that is already out, letting members with unpaid
fees borrow more, and losing track of what is overdue.
Entities
• Member — name, phone, join date, status (active / suspended), running fee balance.
• Item — name, category, replacement value, condition note, status (see state machine).
• Loan — member, item, reserved_at, checked_out_at, due_at, returned_at, fee_charged.
• Payment — member, amount, paid_at, note (used to clear fees).
Business rules
1 Item states: Available → Reserved → Checked Out → Available; from Checked Out an item
becomes Overdue automatically once due_at passes (computed, not a cron); any state may go
to Under Maintenance and back to Available by staff. Invalid transitions must be rejected with
a clear error.
2 A reservation holds an item for 48 hours. If not checked out by then, it expires and the item is
Available again. Expiry must be enforced at read and write time, not only by a background job.
3 Loan period is 7 days from check-out. Late fee is ₹10 per day (calendar days, rounded up),
capped at ₹200 per loan, and never more than the item's replacement value.
4 A member may hold at most 3 active loans (Reserved, Checked Out or Overdue count as active).
5 A member with an unpaid fee balance over ₹100, or with any loan overdue by more than 14
days, cannot reserve or check out.
6 Returning an item computes and records the fee on the loan and adds it to the member's
balance. A return of an item that is not checked out is an error, not a no-op.
7 Suspended members cannot transact; suspension is reversible and keeps history.
Core features
• API: CRUD for members and items; reserve, check out, return, cancel reservation; record
payment; list overdue loans; member statement (loans + fees + payments + balance).
KJBN Labs · Software Engineering Internship · Take-Home Assignment v1.0 · October 2026 Page 2
• UI: item list with status filter and search; item detail with the actions that are valid in its current
state only; member page showing active loans, history, balance and a "why can't this member
borrow?" explanation when blocked; overdue dashboard.
• Time: provide a way for a reviewer to set "today" (e.g. an X-Test-Clock header or an admin
setting) so overdue and expiry logic can be tested without waiting a week. Document it.
Edge cases we will try
Two check-outs of the same item within seconds; returning twice; reserving at 47h59m vs 48h01m;
a fee that would exceed replacement value; a member exactly at ₹100; paying more than the
balance.
Stretch
Waitlist when an item is out, with automatic reservation on return; email/SMS stubs with a visible
outbox; export member statement as PDF.
Reminder of what wins points: correct rules under bad input and concurrency; a clean separation of
API, business rules and persistence; distinct error types with consistent responses; structured logs with
context; boundary tests for every numeric rule; honest README and write-up. See the common PDF,
Section 8.

</details>

## Entry 16

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Request to audit M0 and produce an inspection-and-planning-only implementation plan for Milestone 1 (Domain Model) without editing files. Full prompt below.
- **Answer:** Audited M0, extracted exact M1 deliverables (entities, schema, seed data, rule test stubs), documented domain assumptions, and outlined the M1 plan without modifying files.
- **What I did:** Used as-is to review the proposed M1 architecture and requested refinements.

<details>
<summary>Full prompt text (Entry 16)</summary>

I am working on the KJBN Labs Software Engineering Internship take-home assignment, Problem 1: Equipment Rental Desk.
Project location: D:\files\KJBN\Equipment_rental_desk
GitHub repository: [https://github.com/AbinayaB04/Equipment_rental_desk](https://github.com/AbinayaB04/Equipment_rental_desk)
Current milestone: M0 — Scaffold, committed and pushed.
Next milestone: M1 — Domain model.
I have provided the complete assignment requirements, including Problem 1 and the Common Instructions and Evaluation Criteria. Follow those requirements strictly. Complete all Core features before attempting any Stretch features.
Important rule for every interaction
Whenever I give you a prompt or instruction for this project:
Record my actual prompt in the root PROMPTS.md file, in chronological order, under the correct tool name: Google Antigravity.
Add a brief note explaining what you did with your response: used as-is, edited, or rejected. Update this note after the relevant work is reviewed.
Preserve all existing Claude, Copilot, ChatGPT and other AI prompt-log entries. Never replace or fabricate historical entries.
If you cannot update PROMPTS.md immediately, tell me explicitly and provide the exact entry for me to add. Do not claim it was updated unless you actually changed and verified the file.
Include the prompt-log change in the appropriate milestone commit when the milestone work is committed.
What I want you to do now
Inspection and planning only. Do not edit any files yet.
Inspect the repository structure, current Git status, README.md, PROMPTS.md, SUBMISSION.md, backend, frontend, Docker Compose configuration and existing tests.
Confirm what M0 already implements and identify any existing problems.
Identify the exact M1 requirements from the assignment:
Domain entities and relationships.
Database schema and migrations.
Seed data.
Business-rule test cases, which may intentionally fail until M2.
Explain what already exists and propose an implementation plan for M1.
Identify ambiguities that need numbered assumptions in README.md.
List the files you expect to create or modify.
Do not implement M1, install dependencies, run destructive commands, commit, or push during this step. Do not guess missing assignment requirements.
Present your findings and wait for my approval before proceeding.
Explain your findings in beginner-friendly language. I need to understand and defend the implementation during an interview.

</details>

## Entry 17

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Request to revise the M1 plan on seven specific issues: scope discipline, preserving `/health`, honest testing, domain assumptions (expiry, late fees, maintenance, overdue derivation, integer money), avoiding unnecessary DB constraints, and prompt logging. Full prompt below.
- **Answer:** Refined the M1 plan addressing scope boundaries, entity relationships, database constraints, Alembic migration strategy, seed data scenarios, and honest test specifications.
- **What I did:** Used as-is to verify scope and asked for final technical clarifications before approving implementation.

<details>
<summary>Full prompt text (Entry 17)</summary>

Thanks for the M0 audit and M1 plan. Before implementation, please revise the plan with these changes.

1. **Keep M1 within scope.** Focus on domain models, database schema and migrations, seed data, and business-rule test specifications. Do not implement M2 business logic, M3 API endpoints, M4 UI workflows, or M5 deployment work.

2. **Preserve `/health`.** Do not modify the existing health endpoint in M1 unless you demonstrate a concrete dependency required by the new database setup. Database health-check improvements can be considered for M5.

3. **Handle M1 tests honestly.** Keep the existing six M0 tests passing. Add business-rule test specifications appropriate for M1, but do not use `xfail` merely to hide missing functionality or claim unfinished rules pass. Explain exactly which tests run and why any are expected to fail. Prefer tests against clearly defined future service interfaces where practical, without prematurely implementing M2.

4. **Reconsider assumptions.** Verify each proposed assumption against the assignment. In particular:
   - Explain how reservation expiry behaves at exactly 48 hours and immediately after.
   - Clarify what “calendar days, rounded up” means for late fees, and document the chosen interpretation.
   - Do not store `OVERDUE` as an item status; it is derived from a checked-out loan and its due time.
   - Ensure payment and fee-balance design can enforce the stated rules without floating-point money calculations.
   - Explain how an item in maintenance interacts with an existing reservation or checkout before finalizing that assumption.

5. **Avoid unnecessary schema restrictions.** Propose constraints that the database can reliably enforce. Do not add a phone-number format restriction or other business restriction unless it is justified by the assignment or documented as an assumption.

6. **Correct the documentation plan.** Record the actual M0 commit hash in `SUBMISSION.md` if appropriate, but don't mark M1 complete or invent its date or commit hash before implementation and commit.

7. **Prompt logging.** Once I authorize editing, append the actual prompts I provide to `PROMPTS.md` in chronological order. Preserve all previous entries. For each entry, include the tool, date, actual prompt, a concise summary of the response, and whether the response was used as-is, edited, or rejected. If you cannot update the file, tell me and give me the exact entry to add.

For now, do not edit files, install dependencies, commit, or push. Return the revised plan, including the proposed model relationships, constraints, migrations, seed approach, and tests. Wait for my approval.

</details>

## Entry 18

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Request for final clarifications on model constraint tests against PostgreSQL, precise mathematical seed balance invariants, comprehensive loan status/timestamp definitions, maintenance interaction, and separating M2 test specifications from ordinary test collection. Full prompt below.
- **Answer:** Updated the plan with PostgreSQL migration and constraint testing, precise mathematical seed balance invariants, a comprehensive loan status and timestamp state table with concurrent maintenance explanation, and a clean pytest separation avoiding broken collection.
- **What I did:** Used as-is to approve Milestone 1 implementation.

<details>
<summary>Full prompt text (Entry 18)</summary>

The M1 plan is nearly approved. Please make these final clarifications in the plan only. Do not edit files or install dependencies yet.

1. Model constraint tests must genuinely test the constraints against PostgreSQL, or clearly identify any limitations of an alternative test database. Do not claim they pass before running them. Include migration-upgrade testing against PostgreSQL where practical.

2. Make the seed balance invariant precise: for each seeded member, the running balance must equal all recorded fees minus all recorded payments represented by the seed dataset. Rerunning the seed must not duplicate members, items, loans, or payments, and must not silently overwrite unrelated user data.

3. Define valid `Loan.status` and timestamp combinations comprehensively, including RESERVED, CHECKED_OUT, RETURNED, and CANCELLED. Explain how a checked-out loan remains returnable when staff marks its item UNDER_MAINTENANCE. Ensure the model does not incorrectly imply that an item can never be in maintenance while a loan remains open.

4. Keep M2 behavior tests from breaking ordinary M1 test collection because service modules do not exist yet. Separate future test specifications from the default passing M1 suite, or clearly document the separate command and expected failure. Never claim these tests pass before M2 implements the behavior.

Once these clarifications are reflected, present the final plan for approval. Continue to preserve `/health`, keep M1 within scope, and preserve existing prompt-log entries.

</details>

## Entry 19

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Authorization to implement Milestone 1 (M1 only) with specific conditions covering scope, non-destructive idempotent seed data with exact balance invariants, PostgreSQL constraint tests, derived overdue status, loan lifecycle constraints, 48h expiry boundary documentation, maintenance behavior, and documentation updates. Full prompt below.
- **Answer:** Implemented M1: SQLAlchemy 2.0 models, Alembic migrations, PostgreSQL constraint tests, idempotent seed data, M2 behavioral specification contracts, and updated documentation without editing `/health` or committing.
- **What I did:** Used as-is to implement Milestone 1 domain models, schema, migrations, tests, and seed data, approved after targeted review.

<details>
<summary>Full prompt text (Entry 19)</summary>

The M1 plan is approved with the following conditions. Implement **M1 only** in the existing Equipment Rental Desk repository.

1. **Scope:** Implement SQLAlchemy models, database configuration, Alembic migrations, a non-destructive and idempotent seed script, M1 business-rule test specifications, and the necessary README.md, SUBMISSION.md, and PROMPTS.md updates. Do not implement M2 business logic, API endpoints, UI features, or deployment changes.

2. **Seed data:** Use deterministic identifiers and a safe, transactional approach for records owned by the seed script. The script must be safe to rerun without creating duplicates or corrupting existing data. Do not add a destructive `--reset` option. Ensure every seeded member's balance equals total recorded fees minus total recorded payments.

3. **Tests:** Preserve the existing six passing M0 tests. Add PostgreSQL integration tests that run migrations and verify database constraints. If PostgreSQL is unavailable, report the tests as skipped rather than passed. Configure pytest so M2 specification tests are excluded from the ordinary M1 test run, and document a separate command for running those specifications. Do not use `xfail` to disguise unfinished functionality.

4. **Business rules and schema:** Store money as integer paise and timestamps in UTC. Keep overdue status derived from the due date rather than stored as an item status. Implement the planned loan lifecycle constraints, preserve historical records with appropriate foreign-key deletion rules, and avoid adding an unsupported uniqueness or format restriction to member phone numbers.

5. **Reservation expiry:** Keep the 48-hour expiry boundary explicit: a reservation is valid at 47 hours 59 minutes and expired at exactly 48 hours. Document that an expired reservation's stored item status may temporarily remain `RESERVED` until M2 read/write logic reconciles it.

6. **Maintenance:** Follow the agreed maintenance behavior. A reservation moved into maintenance is cancelled; an item already checked out can be marked for maintenance while its open loan remains returnable. After return, the item remains under maintenance.

7. **Prompt logging:** Preserve all existing PROMPTS.md entries. Add the actual project prompts in chronological order, with the tool name, date, a concise summary of the response, and whether the response was used as-is, edited, or rejected. Do not fabricate historical prompts.

8. **Documentation:** Update the M0 entry in SUBMISSION.md to reference commit `2f56c06` only after verifying it. Do not invent an M1 commit hash or mark M1 complete before it is committed.

9. **Review before committing:** After implementation, show me the changed-file list, complete Git diff, migration details, seed behavior, and test results. Do not commit or push yet. Do not begin M2 until I review and approve the M1 implementation.

Keep the existing `/health` endpoint unchanged. Work incrementally and explain any deviations from the approved plan.

</details>

## Entry 20

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Request to review the completed M1 implementation before any commit or push. Full prompt below.
- **Answer:** Audited source code, models, migrations, PostgreSQL constraint tests, seed script idempotency, and reported findings without modifying files.
- **What I did:** Used as-is to inspect M1 implementation.

<details>
<summary>Full prompt text (Entry 20)</summary>

Review the completed M1 implementation before any commit or push. Do not modify files yet.

Please inspect the actual source code and provide evidence for these checks:

1. **Seed script:** The current script skips insertion if the seed dataset already exists. Verify what happens if only some seed records exist or if existing seed records have inconsistent balances. Does the script detect and report the inconsistency safely? Do not delete existing data or add a destructive reset option.

2. **Database models and migration:** Check that all four models, foreign keys, status enums, lifecycle constraints, indexes, and money constraints match the approved M1 plan. Confirm that money is stored as integer paise and timestamps are timezone-aware UTC.

3. **PostgreSQL integration tests:** Inspect `test_models_postgres.py` and confirm each test actually attempts an invalid database operation and verifies that PostgreSQL rejects it. Confirm the tests use a transaction or cleanup strategy that leaves the database usable after a failed constraint check.

4. **Reservation and loan lifecycle:** Verify the loan timestamp constraints for all four states: RESERVED, CHECKED_OUT, RETURNED, and CANCELLED. Confirm that overdue is derived rather than persisted as an item status.

5. **Test results:** Explain the 14 passing default tests and 16 intentionally failing M2 specifications. Confirm that the M2 tests are excluded from the normal suite by pytest configuration, not merely by their marker declaration.

6. **Prompt log:** Verify that PROMPTS.md preserves all earlier entries and that Entries 13–19 contain actual prompts sent to the tools, rather than reconstructed or invented prompts.

7. **Git and scope:** Confirm `/health` is unchanged and no M2 business logic, API features, UI features, or deployment changes were added. Show the actual `git diff --check`, `git status`, and changed-file summary.

For every item, report PASS, ISSUE, or NEEDS VERIFICATION with evidence from the code. Do not claim a check passed based only on the previous summary. Do not commit or push. After the audit, wait for my approval.

</details>

## Entry 21

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Instruction to make two targeted M1 review corrections (seed dataset completeness verification and PROMPTS.md whitespace) without committing. Full prompt below.
- **Answer:** Enhanced seed.py completeness check and balance invariant audit, resolved trailing whitespace in PROMPTS.md, and ran tests.
- **What I did:** Used as-is to make the two targeted M1 review corrections.

<details>
<summary>Full prompt text (Entry 21)</summary>

Make the two targeted M1 review corrections only. Do not commit or push yet.

1. **Seed verification:** Update `backend/scripts/seed.py` so that when seed records already exist, it checks whether the expected seed dataset is complete and verifies each seed member's balance against the sum of their loan fees minus their payments. If the dataset is partial or inconsistent, print a clear warning describing the problem. Do not insert missing records automatically into an existing partial dataset, overwrite balances, delete records, or add a destructive reset option. Preserve the current behavior for a clean database and safe repeated execution.

2. **PROMPTS.md whitespace:** Fix the `git diff --check` warning on line 241 without changing the actual wording or content of the recorded prompt. Preserve the prompt verbatim. If necessary, use a clearly documented representation that retains the original prompt text.

3. Run the relevant seed checks, verify balance consistency, run the default pytest suite against PostgreSQL, run `ruff check .`, run `ruff format --check .`, and run `git diff --check`. Report actual results and any skipped tests honestly.

4. Show me the final diff and Git status. Do not stage, commit, or push anything. Wait for my approval before committing M1.

Do not modify models, migrations, API routes, UI, or deployment configuration as part of these corrections.

</details>

## Entry 22

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Request for one final targeted review of M1 (restoring verbatim prompts in PROMPTS.md, verifying all seed entities in seed.py, running quality checks, and reporting diffs). Full prompt below.
- **Answer:** Restored verbatim prompts in Entries 15-19, expanded seed.py to check all 4 seed entity types, ran tests, and reported final diffs.
- **What I did:** Used as-is to restore prompt text and seed dataset verification.

<details>
<summary>Full prompt text (Entry 22)</summary>

Perform one final, targeted review of M1. Do not commit, stage, or push.

1. In `PROMPTS.md`, inspect Entries 15–19. The current diff contains placeholders such as `... [Full text of prompt]`. Restore the actual complete prompts from available conversation history or other verifiable records. Do not invent or reconstruct text and label it verbatim. If an original prompt cannot be recovered, accurately label the entry as a summary and state that the full text is unavailable. Preserve Entries 1–14 and all other historical content.

2. In `backend/scripts/seed.py`, verify completeness of the entire seed dataset, not just the eight members. Check the expected seed members, items, loans, and payments using stable identifiers or another reliable method. If related records are missing or existing balances are inconsistent, print a clear warning and skip all insertion or modification. Do not delete, overwrite, or automatically repair existing data. Preserve clean-database seeding and safe reruns.

3. Run the default PostgreSQL-backed pytest suite, `ruff check .`, `ruff format --check .`, `git diff --check`, and the frontend build if relevant files have changed. Report actual command results, including skipped tests.

4. Show the final diff for `PROMPTS.md` and `backend/scripts/seed.py`, plus `git status`. Do not stage, commit, or push. Wait for approval.

Do not change models, migrations, APIs, UI, or deployment configuration.

</details>

## Entry 23

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Targeted verification instruction before commit: inspect PROMPTS.md on disk for placeholders in Entries 13-19, verify seed.py consistency and constraints, verify M1 scope and migrations on a clean database, and report outputs without committing. Full prompt below.
- **Answer:** Verified PROMPTS.md on disk line-by-line, verified seed consistency and constraints against PostgreSQL, verified clean migration upgrade and teardown, and confirmed clean quality checks.
- **What I did:** Used as-is to verify M1 before commit approval.

<details>
<summary>Full prompt text (Entry 23)</summary>

Before committing or pushing M1, perform a targeted verification and fix only confirmed issues.

1. **PROMPTS.md integrity**
   - Inspect the actual current file on disk.
   - Search Entries 13–19 for placeholders such as `[...]`, `...`, or text claiming content was restored instead of containing the actual prompt.
   - Restore missing prompt bodies from the recorded Antigravity session transcript, preserving the exact original user prompts and chronological order.
   - Do not fabricate missing historical prompts or replace full prompts with summaries.
   - Verify the final file and report which entries were checked.

2. **Seed-data consistency**
   - Inspect the complete `backend/scripts/seed.py`, not a truncated diff.
   - Verify every active loan references a distinct item, and that item statuses agree with the associated loan states.
   - Check all seeded member balances against recorded fees minus payments.
   - Check the reserved, checked-out, overdue, returned, cancelled, and maintenance examples against the M1 model constraints.
   - Verify rerunning the seed script does not create duplicates or modify existing data.
   - Add or adjust tests only where a confirmed issue requires it.

3. **M1 scope and tests**
   - Confirm M1 changes are limited to models, database setup, migrations, seed data, business-rule specification tests, and relevant documentation/prompt-log updates.
   - Run the PostgreSQL-backed tests, default pytest suite, Ruff checks, formatter check, frontend production build, and `git diff --check`.
   - Clearly report any skipped tests, deselected tests, or unavailable database services.
   - Inspect the migration for correctness and verify it can be applied to a clean database.
   - Check `README.md` and `SUBMISSION.md` for accurate milestone status and commit references.

Do not commit, push, or start M2. Do not make unrelated refactors. Show the actual fixes, test outputs, and final `git status` when finished.

</details>

## Entry 24

- **Tool:** Google Antigravity
- **Date:** 2026-10-17
- **Prompt:** Approval of M1 review with pre-commit checklist (review staged diff, confirm prompt log, run git diff --cached --check, exclude generated/secret files) and instruction to create the M1 milestone commit using Conventional Commit format with [M1], verify status, and push to main. Full prompt below.
- **Answer:** Created M1 milestone commit feat(domain): [M1] implement domain models, migrations, and seed data, verified git status and commit, and pushed to origin/main.
- **What I did:** Used as-is to stage, commit, and push Milestone 1.

<details>
<summary>Full prompt text (Entry 24)</summary>

M1 review approved based on the reported verification results.

Before committing:
1. Review the complete staged diff and confirm it contains only intended M1 changes.
2. Confirm `PROMPTS.md` preserves all previous entries and contains the actual recorded prompts, not summaries or placeholders.
3. Run `git diff --cached --check` after staging.
4. Do not include generated files, secrets, local environment files, or unrelated changes.

Then create the M1 milestone commit using the repository's Conventional Commit format, including `[M1]` in the commit message. Verify the commit and working-tree status, and push it to the existing `main` branch.

Do not start M2. Report the exact commit hash, push result, and final Git status.

</details>
