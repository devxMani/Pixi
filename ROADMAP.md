# Pixi roadmap

Milestones are complete only when code and reproducible evidence support them.

## Phase 0 — Preserve and inspect baseline
- [x] Preserve the exported HTML prototype.
- [x] Document project intent and prototype limitations.
- [x] Create GitHub repository and version the baseline.
- [ ] Tag the baseline commit and complete a security/dependency/API audit.
- [ ] Inventory prototype actions and runtime assumptions.

## Phase 1 — Evaluation correctness
- [x] Extract a pure evaluation-decision policy into the API scaffold.
- [x] Add tests for target failures, critical regressions, missing observations, empty suites, invalid setup, and not-applicable experiments.
- [x] Add API health and decision endpoint tests.
- [x] Add CI for backend tests and lint.
- [ ] Expand tests for malformed inputs, partial runs, retries, nondeterminism, and all state transitions.

## Phase 2 — Durable backend
- [ ] Choose database hosting and add migrations.
- [ ] Model projects, agent versions, scenarios, suites, runs, observations, candidates, decisions, and evidence metadata.
- [ ] Add transactional run persistence, idempotency, export/restore, and restart tests.
- [ ] Add authentication/project authorization before storing private data.

## Phase 3 — Agent adapter and scenarios
- [ ] Define provider-neutral async adapter contract.
- [ ] Implement fake adapter for normal CI.
- [ ] Build a minimal scenario runner with explicit preconditions and assertions.
- [ ] Choose the first real voice-agent runtime from the existing agent stack.
- [ ] Add bounded, opt-in live tests with strict spend/time limits.

## Phase 4 — Product workflow
- [ ] Connect the existing UI to API-backed run history.
- [ ] Make simulated and live evidence visually unambiguous.
- [ ] Show transcripts/events/latency and trace references where available.
- [ ] Implement candidate diffs and human-reviewed decisions.
- [ ] Demonstrate one reproducible accepted improvement and one reproducible rejected regression.

## Phase 5 — Product hardening
- [ ] Data redaction and retention controls.
- [ ] Usage and budget tracking where provider data permits.
- [ ] Observability, backups, operational docs, and deployment.
- [ ] External user testing and scope refinement.

## Guardrails
- Do not accept a candidate without a completed target and required regression suite.
- Provider/evaluator errors are inconclusive, never passes.
- Keep production mutation behind human approval.
- Do not claim real agent integration until actual external-agent runs are captured.
- Do not add microservices/Kubernetes before workload requires them.
