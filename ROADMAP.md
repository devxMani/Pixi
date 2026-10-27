# Pixi roadmap

This roadmap separates what exists in the exported browser artifact from future product work. Milestones should be considered complete only when supported by code and reproducible evidence.

## Phase 0 — Preserve the baseline

- [x] Export the existing single-page Pixie artifact into `index.html`.
- [x] Document the product intent, prototype limitations, and planned direction.
- [ ] Create the GitHub repository named `Pixi` and push this baseline.
- [ ] Tag the baseline commit so later refactors can be compared against it.
- [ ] Review the full HTML/JavaScript for artifact-specific APIs, unsafe assumptions, and secrets before making the repository public.

**Exit criteria:** the source is versioned and recoverable; no secrets are committed; the baseline can be opened locally with known limitations documented.

## Phase 1 — Understand and test the prototype

- [ ] Inventory the current tabs, actions, state stores, and model calls.
- [ ] Separate deterministic engine logic from DOM/UI code.
- [ ] Identify which storage features depend on the Claude artifact runtime.
- [ ] Add reproducible tests for assertions, versioning, candidate application, regression gates, rejection, and rollback.
- [ ] Distinguish unit-test results, browser checks with fakes, and real-provider evidence.
- [ ] Add a short architecture diagram and a list of known limitations.

**Exit criteria:** the core evaluation behavior can be tested outside the hosted artifact, and no test double is reported as live validation.

## Phase 2 — Durable backend and data model

- [ ] Create a small FastAPI service.
- [ ] Define database migrations for projects, agent versions, scenarios, experiment runs, observations, candidates, decisions, and evidence metadata.
- [ ] Use PostgreSQL for durable state; do not rely on browser storage as the source of truth.
- [ ] Implement API authentication and project-level authorization before storing private customer data.
- [ ] Add idempotent writes, pagination, schema validation, error handling, and export/restore.
- [ ] Add integration tests for restart/reload persistence, concurrent writes, partial failures, and restore behavior.

**Exit criteria:** saved evidence survives application redeployments and can be exported and restored with integrity checks.

## Phase 3 — Reliable evaluation loop

- [ ] Define a provider-neutral interface for running an agent scenario and collecting a response/trace.
- [ ] Require explicit target assertions and independent regression cases.
- [ ] Enforce baseline preconditions; label invalid setups rather than counting them as passes.
- [ ] Treat provider errors and rate limits as missing observations, not passes or failures.
- [ ] Use bounded retries and resumable runs without repeating successful observations.
- [ ] Store raw observations, evaluation outputs, configuration/version hashes, timestamps, and provider/model identifiers when available.
- [ ] Keep acceptance rules conservative: target fixed, regression suite complete, no critical safety regression.
- [ ] Support explicit statuses: passed/validated, rejected, inconclusive, invalid setup, and not applicable.
- [ ] Add tests for nondeterminism and distinguish observed correlation from causal claims.

**Exit criteria:** one reproducible accepted improvement and one reproducible rejected regression, with auditable evidence and v1 preserved.

## Phase 4 — Connect one real voice agent

- [ ] Choose the first runtime/provider based on the user's existing agent and available credentials (candidate options: LiveKit or Pipecat; hosted providers may be considered).
- [ ] Implement a server-side adapter; keep provider secrets out of the browser.
- [ ] Capture real transcripts and relevant tool events, interruption/barge-in events, timestamps, errors, and latency where supported.
- [ ] Clearly document what the adapter can and cannot observe.
- [ ] Add a small opt-in live test suite with call/time/budget limits.
- [ ] Test failures such as silence, interruptions, tool errors, latency spikes, and safety regressions.

**Exit criteria:** Pixi evaluates an external agent rather than only its built-in demo agent, and reports evidence from actual calls.

## Phase 5 — Product hardening

- [ ] Add user accounts, project isolation, and access control.
- [ ] Add redaction, retention settings, and explicit handling of audio/transcript privacy.
- [ ] Add usage/cost tracking and per-project budgets where provider data allows it.
- [ ] Add CI for linting, type checks, unit tests, integration tests, and build checks.
- [ ] Deploy frontend, backend, and database separately with environment-specific configuration.
- [ ] Add observability, backups, migration/rollback procedures, and operational docs.
- [ ] Write a clear demo flow and publish a roadmap based on user feedback.

**Exit criteria:** a small number of users can safely run repeatable evaluations and inspect history without depending on one browser session.

## Decisions still open

- Frontend migration approach and framework.
- First real voice runtime/provider.
- Model providers and evaluation model(s).
- Authentication and deployment providers.
- License and repository visibility.
- Data retention and whether raw audio is ever stored (default recommendation: avoid storing raw audio unless necessary and explicitly consented to).

## Non-goals for the first product milestone

- Kubernetes or microservices before real usage requires them.
- Supporting every voice platform at once.
- Automatic production prompt changes without review and regression gates.
- Claiming production readiness based only on mocked tests or a demo.
