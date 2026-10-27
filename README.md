# Pixi

**A reliability workspace for voice agents. Find failures, reproduce them, and verify fixes against regression suites.**

Pixi is an early-stage project exploring a closed-loop testing and reliability workflow for voice agents: scenario execution, evidence-backed failure analysis, small reversible candidate changes, and conservative regression-gated decisions.

> Status: early prototype plus the first API-backed local workspace. The Miso UI is preserved at the root page. The Reliability Workspace supports projects, scenarios, simulated fixture runs, saved observations, assertion results, run history, candidate evaluations, human review, versioned JSON project exports, and a configurable HTTP bridge. Pixi provides a bridge contract, but no specific vendor/runtime is verified until an operator configures and validates its adapter.

## Product direction

The MVP is for engineers building or operating voice agents who need to investigate interruptions, tool failures, latency, response quality, and safety regressions. The core promise is: know what broke, reproduce it, and prove a fix does not regress the agent.

See Product specification at docs/PRODUCT_SPEC.md, Architecture at docs/ARCHITECTURE.md, Prototype audit at docs/PROTOTYPE_AUDIT.md, Roadmap at ROADMAP.md, Engineering guide at docs/ENGINEERING_GUIDE.md, and Contributing at CONTRIBUTING.md.

## Run locally

Requires Python 3.11+.

1. Change directory to `backend`.
2. Create and activate a Python virtual environment.
3. Install development dependencies with `pip install -e '.[dev]'`.
4. Set `APP_ENV=development` in your local shell.
5. Run `alembic upgrade head`.
6. Run `uvicorn app.main:app --reload`.
7. Open http://127.0.0.1:8000 for the original Miso prototype or http://127.0.0.1:8000/console.html for the API-backed Reliability Workspace.

The API docs are at http://127.0.0.1:8000/docs and the health endpoint is http://127.0.0.1:8000/health.

Tests: run `pytest` from `backend`. Lint: run `ruff check app tests` from `backend`.

## Current functionality

- Evidence policy distinguishes passed, failed, inconclusive, invalid_setup, and not_applicable outcomes.
- Scenario assertions cover response text, prohibited phrases, latency limits, and tool-call expectations.
- Projects, scenarios, runs, observations, checks, candidate proposals, evaluations, and review decisions persist through SQLAlchemy/Alembic.
- The workspace shows persisted run history and evidence provenance.
- `GET /api/v1/projects/{project_id}/export` returns a versioned JSON snapshot of a project's scenarios, runs, observations, checks, candidates, evaluations, and review history.
- `POST /api/v1/projects/import` validates that snapshot's reference graph and restores it as a separate project, remapping project/scenario/run/candidate IDs and all saved evidence references. It does not overwrite the source project or execute candidate changes.
- Supplying an `Idempotency-Key` header on a demo-run request makes retries return the original run; reusing the same key for different input returns HTTP 409.
- A fixture run is clearly marked simulated. Exported data does not convert simulated evidence into live evidence.
- A configurable server-side HTTP JSON bridge can execute baseline and candidate-variant scenarios through `POST /api/v1/projects/{project_id}/scenarios/{scenario_id}/agent-runs` (`?candidate_id=...` selects a candidate variant). It follows the strict protocol in `docs/AGENT_BRIDGE.md`; it is not a vendor-specific integration.
- Candidate gate evaluations use persisted run IDs and immutable agent versions. They require a failed baseline target, a passing candidate target, and passing candidate runs for every non-target scenario in the project. Critical regressions block approval; partial suites, mixed candidate versions, and fixture evidence cannot satisfy the live gate.
- Restore preserves historical evidence and review decisions but does not re-run agents or apply candidates. Older exports without immutable agent versions remain ineligible for the versioned live-candidate gate.

## Safety and limitations

The API defaults to disabled unless `APP_ENV=development`. This is intentionally local-development-only because authentication and project authorization are not implemented yet. Never expose this development API publicly or use it for real customer transcripts/audio. Provider credentials must remain server-side. Data redaction, retention controls, rate limiting, provider-specific runtime integration, and production deployment hardening remain future work.

## Near-term build plan

1. Configure or build a trusted bridge for the first real voice-agent runtime; follow `docs/AGENT_BRIDGE.md`.
2. Add provider/runtime-specific support for real audio, interruption, VAD/endpointing, and tool trace events.
3. Add agent-version history and restore/import, then bind candidate checks to recorded live runs.
4. Add authentication/project isolation and data handling controls before any shared deployment.
5. Expose live-run and provenance controls in the workspace, then validate them against an actual agent.

## License

No license has been selected. Until one is added, do not assume others have permission to reuse or redistribute the code.
