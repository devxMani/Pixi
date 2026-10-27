# Pixi

**A reliability workspace for voice agents. Find failures, reproduce them, and verify fixes against regression suites.**

Pixi is an early-stage project exploring a closed-loop testing and reliability workflow for voice agents: scenario execution, evidence-backed failure analysis, small reversible candidate changes, and conservative regression-gated decisions.

> Status: early prototype plus the first API-backed local workspace. The Miso UI is preserved at the root page. The Reliability Workspace now supports projects, scenarios, simulated fixture runs, saved observations, assertion results, and run history. It still does not connect to a real voice agent. Do not treat simulated runs as live-provider evidence.

## Product direction

The MVP is for engineers building voice agents who need to investigate interruptions, tool failures, latency, response quality, and safety regressions. The core promise is: know what broke, reproduce it, and prove a fix does not regress the agent.

See Product specification at docs/PRODUCT_SPEC.md, Architecture at docs/ARCHITECTURE.md, Prototype audit at docs/PROTOTYPE_AUDIT.md, Roadmap at ROADMAP.md, Engineering guide at docs/ENGINEERING_GUIDE.md, and Contributing at CONTRIBUTING.md.

## Run locally

Requires Python 3.11+.

1. Change directory to backend.
2. Create and activate a Python virtual environment.
3. Install development dependencies with pip install -e '.[dev]'.
4. Set APP_ENV=development in your local shell.
5. Run alembic upgrade head.
6. Run uvicorn app.main:app --reload.
7. Open http://127.0.0.1:8000 for the original Miso prototype or http://127.0.0.1:8000/console.html for the API-backed Reliability Workspace.

The API docs are at http://127.0.0.1:8000/docs and the health endpoint is http://127.0.0.1:8000/health.

Tests: run pytest from backend. Lint: run ruff check app tests from backend.

## Current functionality

- Evidence policy distinguishes passed, failed, inconclusive, invalid_setup, and not_applicable outcomes.
- Scenario assertions cover response text, prohibited phrases, latency limits, and tool-call expectations.
- Projects, scenarios, runs, observations, and checks persist through SQLAlchemy/Alembic.
- The workspace shows persisted run history and the source of evidence.
- The fixture runner is explicitly simulated; no model call, phone call, or external agent is made.

## Safety and limitations

The API defaults to disabled unless APP_ENV=development. This is intentionally local-development-only because authentication and project authorization are not implemented yet. Never expose this development API publicly or use it for real customer transcripts/audio. Provider credentials must remain server-side. Data redaction, retention controls, rate limiting, candidate/version persistence, and production deployment hardening remain future work.

## Near-term build plan

1. Choose the first real voice-agent runtime to evaluate.
2. Implement a server-side adapter with evidence provenance and bounded live tests.
3. Add candidate patches, version history, regression gates, and human approval.
4. Add authentication/project isolation and data handling controls.
5. Connect real-agent history and evidence to the workspace.

## License

No license has been selected. Until one is added, do not assume others have permission to reuse or redistribute the code.
