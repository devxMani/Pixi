# Pixi product spec

## Product thesis
Pixi is a reliability workspace for voice-agent teams. It turns real agent conversations and reproducible scenarios into actionable failures, then evaluates small, reviewable fixes against target and regression tests.

**Initial user:** an engineer building or operating a voice agent who needs to reproduce failures involving turn-taking, interruptions, tool execution, latency, policy/safety, or response quality.

**Initial promise:** Know what broke, reproduce it, and prove a fix does not regress the agent.

## The first useful workflow
1. Connect one agent runtime using a server-side adapter.
2. Define a scenario with setup, user turns/events, expected outcomes, and safety constraints.
3. Run the same scenario against a pinned agent configuration.
4. Inspect transcript/trace evidence, tool events, timing, and assertion results.
5. Create a proposed change with an explicit hypothesis and diff.
6. Run the target case plus a fixed regression suite.
7. Record validated, rejected, inconclusive, invalid-setup, or not-applicable status.
8. Keep immutable run evidence and version history; require human approval before applying changes.

## MVP scope
### Must have
- Scenario and assertion model with deterministic unit tests.
- Provider-neutral agent adapter interface.
- Run records, observations, logs/evidence metadata, and pinned configuration/version identifiers.
- Target test + regression suite gate.
- Explicit outcome states; infrastructure errors never count as passing.
- Human-reviewed, reversible candidate changes.
- Durable database, migrations, and export.
- Secrets server-side; project isolation before customer data is stored.
- Clear UI states for demo/simulated data vs actual provider evidence.

### Later
- Multiple agent adapters; broad provider coverage.
- Automated diagnosis and candidate generation.
- Audio playback/recording, only with clear consent and retention controls.
- Collaborative review, analytics, cost tracking, alerting, and team management.
- Automatic production rollout (not part of the MVP).

## Evaluation result contract
A run is `passed` only if the target assertions pass and the full required regression suite completes without a critical regression. `failed` means a required assertion failed. `inconclusive` means the provider, evaluator, or required data failed or was unavailable. `invalid_setup` means preconditions were not met. `not_applicable` means the experiment does not apply to this configuration.

Never convert timeout, rate limit, malformed candidate, missing observation, unexecuted regression, or a skipped precondition into a pass.

## Candidate decision policy
- Candidate changes must be small, inspectable, and reversible.
- Run on a pinned baseline.
- Execute target case and regression suite against the same intended configuration.
- Critical safety regression blocks acceptance.
- Incomplete/error runs cannot accept or reject based on absent evidence; classify them as inconclusive.
- Preserve all observations and the reason for the decision.
- Human approval is required before candidate activation.

## Quality bar for claims
A prototype/mock result is not live-provider evidence. A live model call to a demo agent is not proof of external voice-agent integration. A single noisy observation is not causal proof. Public claims about accuracy or improvement require reproducible, inspectable runs and documented methodology.

## Product principles
1. Evidence before claims.
2. Safety and regressions are hard gates.
3. Human approval before changes.
4. Default to minimal sensitive data retention.
5. Errors remain visible.
6. One excellent integration before many shallow ones.
7. Ship a small useful product before infrastructure complexity.
