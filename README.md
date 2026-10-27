# Pixi

**A reliability workspace for voice agents. Find failures, reproduce them, and verify fixes against regression suites.**

Pixi is an early-stage project exploring a closed-loop testing and reliability workflow for voice agents: scenario execution, evidence-backed failure analysis, small reversible candidate changes, and conservative regression-gated decisions.

> Status: early prototype plus the first API scaffold. The browser prototype remains in index.html. The API now persists development projects, scenarios, simulated demo runs, observations, and checks. It still does not connect to a real voice agent. Do not treat simulated runs as live-provider evidence.

## Product direction

The MVP is for engineers building voice agents who need to investigate interruptions, tool failures, latency, response quality, and safety regressions. The core promise is: know what broke, reproduce it, and prove a fix does not regress the agent.

See Product specification at docs/PRODUCT_SPEC.md, Architecture at docs/ARCHITECTURE.md, Prototype audit at docs/PROTOTYPE_AUDIT.md, Roadmap at ROADMAP.md, Engineering guide at docs/ENGINEERING_GUIDE.md, and Contributing at CONTRIBUTING.md.

## Current repository

- index.html — preserved exported browser prototype.
- backend/app/domain/evaluation.py — pure conservative experiment decision policy.
- backend/app/domain/scenarios.py and scenario_runner.py — scenario/assertion contracts and conservative result classification.
- backend/app/adapters/ — provider-neutral adapter protocol plus a fixture adapter explicitly marked simulated.
- backend/app/db.py and models.py — SQLAlchemy database/session and initial data models.
- backend/migrations/ — Alembic schema migration.
- backend/app/main.py — health, project/scenario CRUD, simulated-run, history, and decision endpoints.
- backend/tests/ — policy, scenario, persistence, API, and prototype guardrail tests.
- .github/workflows/backend-ci.yml — backend tests, lint, migration and prototype syntax checks.

## Run the API locally

Requires Python 3.11+.

1. Change directory to backend.
2. Create and activate a Python virtual environment.
3. Install development dependencies with pip install -e '.[dev]'.
4. Set APP_ENV=development in your local shell.
5. Run alembic upgrade head.
6. Run uvicorn app.main:app --reload.

Then open http://127.0.0.1:8000/docs for the interactive API docs; health is at http://127.0.0.1:8000/health.

Tests: run pytest from backend. Lint: run ruff check app tests from backend.

The demo-run endpoint evaluates fixture output, not a real agent. Its evidence is always marked simulated. The API defaults to disabled outside development; use it only locally until authentication and project authorization are implemented.

## Evaluation safety contract

Pixi distinguishes passed, failed, inconclusive, invalid_setup, and not_applicable. A missing observation, provider error, incomplete regression suite, empty regression suite, or invalid precondition cannot be counted as a pass. Critical safety regressions block acceptance.

## Near-term build plan

1. Inventory the HTML prototype and preserve its current behavior.
2. Stabilize testable evaluation rules and CI.
3. Add typed persistence models and database migrations — the first local persistence increment now exists.
4. Add and verify a real voice-agent adapter behind the provider-neutral contract.
5. Implement candidate patches, regression-gated decisions, version history, and human approval.
6. Integrate the UI with durable run/evidence APIs and add authentication/privacy boundaries before customer data is stored.

## Security

Never commit real secrets, call recordings, or private transcripts. Provider credentials must remain server-side. The API is development-only: all /api/v1 routes return 503 unless APP_ENV=development. Authentication, project authorization, rate limiting, retention controls, and deployment hardening are not implemented yet.

## License

No license has been selected. Until one is added, do not assume others have permission to reuse or redistribute the code.
