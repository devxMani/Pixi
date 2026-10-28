# Pixi

**A reliability workspace for voice agents. Find failures, reproduce them, and verify fixes against regression suites.**

Pixi is an early-stage project exploring a closed-loop testing and reliability workflow for voice agents: scenario execution, evidence-backed failure analysis, small reversible candidate changes, and conservative regression-gated decisions.

> Status: early-stage engineering workspace. The original Miso HTML is preserved as a reference baseline; the primary Reliability Workspace now lives in `web/` as a Next.js App Router + TypeScript application. It uses the existing FastAPI evaluation API through a guarded same-origin proxy. Pixi provides a generic bridge contract, but no specific vendor/runtime is verified until an operator configures and validates the adapter against its actual agent.

## Product direction

The MVP is for engineers building or operating voice agents who need to investigate interruptions, tool failures, latency, response quality, and safety regressions. The core promise is: know what broke, reproduce it, and prove a fix does not regress the agent.

See Product specification at docs/PRODUCT_SPEC.md, Architecture at docs/ARCHITECTURE.md, Prototype audit at docs/PROTOTYPE_AUDIT.md, Roadmap at ROADMAP.md, Engineering guide at docs/ENGINEERING_GUIDE.md, and Contributing at CONTRIBUTING.md.

## Run locally

Requires Python 3.11+ and Node.js 20.9+ (Node 22 recommended). The main UI and API run as two local processes.

**Terminal 1 — FastAPI backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export APP_ENV=development
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Next.js UI**

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000 for the Next.js Reliability Workspace. The legacy prototype remains available at http://127.0.0.1:8000 and http://127.0.0.1:8000/console.html. API docs are at http://127.0.0.1:8000/docs and health is at http://127.0.0.1:8000/health.

The web app uses a server-side same-origin proxy. Optionally set `PIXI_API_BASE_URL=http://127.0.0.1:8000/api/v1` in `web/.env.local` if your backend is not at the default address.

**Quality checks**

```bash
# Python backend
cd backend && pytest && ruff check app tests

# Next.js frontend
cd web && npm install && npm run typecheck && npm run lint && npm run build
```

GitHub Actions runs backend tests/migrations and a separate frontend typecheck/lint/build workflow on web changes.

## Current functionality

- Evidence policy distinguishes passed, failed, inconclusive, invalid_setup, and not_applicable outcomes.
- Scenario assertions cover response text, prohibited phrases, latency limits, and tool-call expectations.
- Projects, scenarios, runs, observations, checks, candidate proposals, evaluations, and review decisions persist through SQLAlchemy/Alembic.
- The primary workspace is a Next.js App Router + TypeScript app in `web/`, with strict API contracts, responsive evidence screens, and a same-origin server-side proxy to FastAPI.
- The workspace shows persisted run history and evidence provenance. The earlier HTML console remains available as a reference/fallback.
- `GET /api/v1/projects/{project_id}/export` returns a versioned JSON snapshot of a project's scenarios, runs, observations, checks, candidates, evaluations, and review history.
- `POST /api/v1/projects/import` validates that snapshot's reference graph and restores it as a separate project, remapping project/scenario/run/candidate IDs and all saved evidence references. It does not overwrite the source project or execute candidate changes.
- Supplying an `Idempotency-Key` header on a demo-run request makes retries return the original run; reusing the same key for different input returns HTTP 409.
- A fixture run is clearly marked simulated. Exported data does not convert simulated evidence into live evidence.
- A configurable server-side HTTP JSON bridge can execute baseline and candidate-variant scenarios through `POST /api/v1/projects/{project_id}/scenarios/{scenario_id}/agent-runs` (`?candidate_id=...` selects a candidate variant). It follows the strict protocol in `docs/AGENT_BRIDGE.md`; it is not a vendor-specific integration.
- Candidate gate evaluations use persisted run IDs and immutable agent versions. They require a failed baseline target, a passing candidate target, and passing candidate runs for every non-target scenario in the project. Critical regressions block approval; partial suites, mixed candidate versions, and fixture evidence cannot satisfy the live gate.
- The workspace can run the selected candidate across every saved project scenario in one action. Per-scenario idempotency keys make retries safe if the bridge or UI fails partway through; each run remains inspectable in history before evaluation.
- Restore preserves historical evidence and review decisions but does not re-run agents or apply candidates. Older exports without immutable agent versions remain ineligible for the versioned live-candidate gate.

## Safety and limitations

The API and Next.js API proxy are deliberately disabled for production use until authentication and project authorization are implemented. Run locally with `APP_ENV=development`; never expose the development setup publicly or use it for real customer transcripts/audio. Provider credentials must remain server-side. Data redaction, retention controls, rate limiting, provider-specific runtime integration, and production deployment hardening remain future work.

## Near-term build plan

1. Configure and verify the bridge against the actual voice-agent runtime; follow `docs/AGENT_BRIDGE.md`.
2. Add provider/runtime-specific support for real audio, interruption/barge-in, VAD/endpointing, and detailed tool traces.
3. Demonstrate a reproducible accepted improvement and rejected critical regression on a staged real agent.
4. Add authentication/project isolation, data redaction/retention, and budget/rate limits before any shared deployment.
5. Add named/tagged regression suites rather than treating every saved project scenario as the required suite.

## License

No license has been selected. Until one is added, do not assume others have permission to reuse or redistribute the code.
