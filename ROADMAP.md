# Pixi roadmap

Milestones are complete only when code and reproducible evidence support them.

## Phase 0 — Preserve and inspect baseline

- [x] Preserve the exported HTML prototype.
- [x] Document project intent and prototype limitations.
- [x] Create GitHub repository and version the baseline.
- [x] Normalize branding and strengthen dynamic HTML escaping.
- [x] Add prototype JavaScript syntax validation in CI.
- [ ] Complete a full security/dependency/API audit and inventory every prototype action.

## Phase 1 — Evaluation correctness

- [x] Extract a pure evaluation-decision policy into the API.
- [x] Test target failures, critical regressions, missing observations, empty suites, invalid setup, and not-applicable experiments.
- [x] Define scenario/assertion contracts for transcript text, latency, and tool-call evidence.
- [x] Add a provider-neutral async adapter protocol and explicit simulated fixture adapter.
- [x] Test scenario pass/fail/inconclusive outcomes and adapter errors.
- [x] Run automated tests, lint, migration, and browser JavaScript syntax checks in CI.

## Phase 2 — Durable backend

- [x] Add SQLAlchemy persistence models and an initial Alembic migration.
- [x] Persist projects, scenarios, simulated runs, observations, and assertion results.
- [x] Add API tests for saved history, errors, project scoping, and the development-only guard.
- [x] Serve the original prototype and the API-backed workspace through FastAPI.
- [x] Add a run-history endpoint used by the workspace.
- [x] Persist candidate proposals, evaluation snapshots, and human-review decisions; simulated evidence cannot be approved for release.
- [x] Add retry-safe run creation using idempotency keys.
- [x] Add a versioned JSON export for project evidence and evaluation history.
- [x] Record agent variant/version provenance on saved runs and add versioned JSON backup export/import that remaps evidence references.
- [x] Test restore of project, scenario, run, candidate, evaluation, and human-review history with new IDs.
- [ ] Add process-restart and durable-database backup/restore tests.
- [ ] Add authentication/project authorization before storing private data.

## Phase 3 — Agent adapter and scenarios

- [x] Define a provider-neutral async adapter contract.
- [x] Implement a fixture adapter for deterministic CI; it always emits simulated evidence.
- [x] Add a configurable HTTP JSON bridge adapter and live-run API route with strict response schema, bounded timeouts, and HTTPS requirement outside local development.
- [x] Version the bridge protocol with candidate ID, variant, and immutable agent-version provenance.
- [x] Document the provider-neutral bridge request/response contract.
- [ ] Choose the first real voice-agent runtime from the agent stack to be evaluated and verify a bridge against it.
- [ ] Add runtime-specific support for audio turns, interruptions/barge-in, VAD/endpointing, and detailed tool traces.
- [ ] Add realistic voice events such as barge-in, silence, endpointing, tool events, and latency.
- [ ] Add bounded, opt-in live tests with strict spend/time limits and clear evidence provenance.

## Phase 4 — Product workflow

- [x] Create a local API-backed UI for projects, scenarios, fixture runs, checks, and saved history.
- [ ] Connect real-agent run history to the workspace.
- [ ] Make live-vs-simulated evidence provenance visually unambiguous in every view.
- [x] Implement candidate hypotheses/changes, gate evaluation snapshots, and human-review records; release approval remains locked for simulated evidence.
- [x] Gate a candidate using persisted baseline, candidate-target, and same-version candidate regression runs; fixture/manual checks cannot satisfy the live-evidence gate.
- [ ] Demonstrate one reproducible accepted improvement and one reproducible rejected critical regression against an actual configured staging agent.

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
