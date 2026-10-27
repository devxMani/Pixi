# Pixi architecture (target)

This is a target architecture, not a claim about current implementation.

## High-level components

```text
Browser UI
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
