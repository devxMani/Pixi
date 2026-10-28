# Pixi architecture

This document separates the current local implementation from the intended production architecture.

## Current implementation

- **Frontend:** `web/` is the primary Next.js App Router + TypeScript workspace. It calls the API through `web/app/api/pixi/[...path]/route.ts`, a same-origin server-side proxy. `index.html` and `console.html` remain legacy/reference implementations.
- **Backend:** `backend/app/main.py` owns the FastAPI API, orchestration, persisted run evidence, evaluation gate, project export/import, and human review.
- **Persistence:** SQLAlchemy models and Alembic migrations persist projects, scenarios, run snapshots, observations, checks, candidates, evaluations, and reviews.
- **Agent boundary:** the HTTP JSON adapter is generic. It becomes a real integration only when configured against a trusted bridge that actually runs the chosen agent and returns observed output plus immutable version metadata.
- **Deployment posture:** API routes return 503 unless `APP_ENV=development`; the Next.js proxy also refuses production-mode requests. This fail-closed posture is deliberate until authentication and project authorization exist. The app is not yet production deployable.

## Intended high-level components

## High-level components

```text
Next.js App Router UI
   |
   v
Same-origin server proxy (development only)
   |
   v
FastAPI application ---- Authentication / project authorization
   |                              |
   v                              v
Run orchestrator ------------ PostgreSQL
   |
   +--> Scenario runner
   |       |
   |       +--> Agent adapter (first real runtime, chosen after inspecting the current agent stack)
   |       +--> Evidence collector (transcript, tool events, timing, errors)
   |
   +--> Assertion evaluator
   |
   +--> Regression gate
   |
   +--> Decision record (passed / failed / inconclusive / invalid_setup / not_applicable)
```

## Initial deployment shape
Start with a modular monolith: one frontend, one API service, one PostgreSQL database. Do not add queues, microservices, Kubernetes, or a dedicated worker until measured workload justifies them. Long-running live sessions may later be delegated to a worker/queue.

## Frontend organization

- `web/app/page.tsx` provides the entry page and `web/app/workspace.tsx` owns the current interactive workspace.
- `web/lib/types.ts` mirrors the API's public data contracts; keep those types aligned when API schemas change.
- `web/lib/api.ts` is the typed same-origin API client.
- `web/app/api/pixi/[...path]/route.ts` forwards only same-origin GET/POST API requests to the configured FastAPI base URL. It rejects malformed path segments, refuses redirects, applies a local request-body cap, and is disabled when Next is running in production mode.
- `web/app/globals.css` owns reusable responsive design tokens and components. Keep new UI components typed and accessible; do not expose provider credentials through client bundles.

## Core entities
- **Project**: tenant boundary and settings.
- **AgentConnection**: adapter kind and non-secret configuration; credential references are stored separately from ordinary config.
- **AgentVersion**: pinned agent configuration and version hash.
- **Scenario**: named test, steps/events, preconditions, assertions, tags, and safety severity.
- **Suite**: ordered or grouped set of scenarios and required gates.
- **Run**: execution envelope, status, timestamps, version/config hash, and reproducibility metadata.
- **Observation**: one attempt's output, events, timing, provider metadata, and error state.
- **Candidate**: proposed patch/config change, hypothesis, author, and reversibility metadata.
- **Decision**: outcome, gate results, rationale, approver, and links to supporting observations.
- **EvidenceArtifact**: metadata and optional sanitized payload references. Avoid raw audio by default.

## Trust boundaries
- Browser inputs are untrusted.
- Provider credentials never reach browser code or logs.
- Project authorization is checked on every resource read/write.
- Transcript/tool payloads may contain secrets or personal information and need redaction/retention rules.
- Candidate-generated text is data, not executable code.
- No candidate is applied to production automatically in the MVP.

## API sketch
- `GET /health`
- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET/POST /api/v1/projects/{project_id}/scenarios`
- `POST /api/v1/projects/{project_id}/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/observations`
- `POST /api/v1/runs/{run_id}/decisions`
- `GET /api/v1/projects/{project_id}/versions`

Do not implement endpoints that imply live execution until an actual agent adapter is available. Until then, use explicit fixtures and label them `simulated`.

## Persistence and reliability
- Use migrations.
- Use foreign keys and constraints.
- Use transactions for run state transitions and decisions.
- Use idempotency keys for run creation once retries are introduced.
- Store timestamps in UTC.
- Distinguish durable records from expiring artifacts.
- Include export/restore tests before production use.
