# Pixi roadmap

Milestones are complete only when code and reproducible evidence support them.

## Phase 0 — Preserve and inspect baseline

- [x] Preserve the exported HTML prototype.
- [x] Document project intent and prototype limitations.
- [x] Create GitHub repository and version the baseline.
- [x] Normalize branding and strengthen dynamic HTML escaping.
- [x] Add prototype JavaScript syntax validation in CI.
- [ ] Tag the baseline and complete a full security/dependency/API audit.
- [ ] Inventory every prototype action and runtime assumption.

## Phase 1 — Evaluation correctness

- [x] Extract a pure evaluation-decision policy into the API.
- [x] Test target failures, critical regressions, missing observations, empty suites, invalid setup, and not-applicable experiments.
- [x] Define scenario/assertion contracts for transcript text, latency, and tool-call evidence.
- [x] Add a provider-neutral async adapter protocol and explicit simulated fixture adapter.
- [x] Test scenario pass/fail/inconclusive outcomes and adapter errors.
- [x] Add CI for tests, lint, migration, and prototype syntax checks.
- [ ] Expand tests for retries, nondeterminism, and every experiment state transition.

## Phase 2 — Durable backend

- [x] Add SQLAlchemy persistence models and an initial Alembic migration.
- [x] Persist projects, scenarios, simulated runs, observations, and assertion results.
- [x] Add API tests for saved history, errors, project scoping and the development-only guard.
- [ ] Add candidate/version/decision persistence, idempotency, export/restore and restart tests.
- [ ] Add authentication/project authorization before storing private data.

## Phase 3 — Agent adapter and scenarios

- [x] Define a provider-neutral async adapter contract.
- [x] Implement a fixture adapter for deterministic CI; it always emits simulated evidence.
- [ ] Choose the first real voice-agent runtime from the agent stack to be evaluated.
- [ ] Implement a server-side adapter for a real external runtime.
- [ ] Add realistic voice events such as barge-in, silence, endpointing, tool events, and latency.
- [ ] Add bounded, opt-in live tests with strict spend/time limits and clear evidence provenance.

## Phase 4 — Product workflow

- [ ] Connect the existing UI to API-backed project, scenario, and run history.
- [ ] Make simulated and live evidence visually unambiguous in every view.
- [ ] Show transcripts, events, latency and trace references where available.
- [ ] Implement candidate diffs and human-reviewed decisions.
- [ ] Demonstrate one reproducible accepted improvement and one reproducible rejected regression.

## Phase 5 — Product hardening

- [ ] Data redaction and retention controls.
- [ ] Usage and budget tracking where provider data permits.
- [ ] Authentication, project isolation, rate limits and abuse protection.
- [ ] Observability, backups, operational docs and deployment.
- [ ] External user testing and scope refinement.

## Guardrails

- Never accept a candidate without a completed target and required regression suite.
- Provider/evaluator errors are inconclusive, never passes.
- Keep production mutation behind human approval.
- Never claim real-agent integration until external-agent runs are captured and can be inspected.
- Do not add microservices or Kubernetes before workload requires them.
