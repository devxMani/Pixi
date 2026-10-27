# Pixi

**A self-improving evaluation and reliability workspace for voice agents.**

Pixi is an early-stage project exploring a closed-loop workflow for testing voice-agent behavior, finding failures, proposing small reversible changes, evaluating candidates against regression tests, and keeping evidence about version decisions.

> **Project status: prototype.** The current checked-in application is a single-page HTML artifact. It is not yet a production voice-agent platform. Some parts of the experience are simulated, and browser-local state is not a durable production data store. See [Current state](#current-state) and the [roadmap](docs/ROADMAP.md).

## Why Pixi?

Voice agents can fail in ways that ordinary request/response tests miss: interruption handling, confusing responses, tool-call errors, latency spikes, and safety regressions. Pixi aims to make those failures reproducible and make every proposed improvement prove that it fixes the target without breaking previously passing behavior.

## Intended evaluation loop

1. **Run** a set of explicit scenarios against the active agent version.
2. **Detect** a failure using assertions and saved evidence.
3. **Diagnose** the failure and cite the relevant response or trace evidence.
4. **Propose** one small, reversible candidate change.
5. **Evaluate** the target scenario and the regression suite, with repeated observations where appropriate.
6. **Decide** to accept, reject, or mark the experiment inconclusive. Missing data, provider errors, or incomplete regression runs must never count as passes.
7. **Version and preserve** the decision, observations, and previous version so changes can be reviewed and rolled back.

## Current state

The current `index.html` is the exported Pixie browser artifact. It contains a dashboard-style console with **Ready, Test, Bench, Secure, Build, Monitor, and Improve** areas, plus the Miso cat demo.

The artifact's own “What is real” section distinguishes the current implementation as follows:

- **Implemented in the prototype:** assertion checks, regression comparison, accept/reject policy, version history and rollback, and Claude model calls when the hosted artifact's live-mode sample capability is available.
- **Simulated / not a production integration:** default agent behavior, rule-based diagnosis and candidates, noise/accent variants, call log, and “marking live”.
- **Not yet implemented as a product:** external voice-agent connection, real audio callers, token-cost accounting, and a server-side persistent store.

These are descriptions of the prototype, not claims of production readiness. Test counts reported by the hosted artifact should be independently rerun after migration; scripted tests and stand-in samplers are not real-model evidence.

## Quick start

At this stage, the frontend is a standalone HTML file and needs no package installation:

1. Clone or download this repository.
2. Open `index.html` in a modern browser, or serve the folder locally with any static HTTP server.
3. Treat browser-based experiment history as disposable until server-side persistence is implemented and verified.

The exported artifact may rely on browser APIs or hosted-artifact capabilities that behave differently outside Claude. Live model access, durable storage, and artifact-specific permissions are **not guaranteed** to work when opened locally. Do not put API keys into `index.html`.

## Planned architecture

- **Web UI:** migrate the existing interface incrementally to React + TypeScript once behavior is understood and covered by tests.
- **API:** Python + FastAPI for experiment orchestration, model-provider adapters, evaluation runs, and version decisions.
- **Evaluation engine:** explicit assertions, target checks, regression suites, failure classification, retries, and evidence records.
- **Persistence:** PostgreSQL with schema migrations for projects, agent versions, scenarios, runs, observations, candidate changes, and decisions.
- **Voice integration:** begin with one real provider/agent runtime (LiveKit or Pipecat; finalize after inspecting requirements), then add other adapters behind a common interface.
- **CI:** automated unit and integration tests; live-model tests are opt-in, budget-limited, and clearly distinguished from deterministic tests.

The architecture is a plan, not an implemented stack. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Development principles

- Never label simulated results as live evidence.
- Never accept a candidate when required evaluation data is missing or errored.
- Keep safety/regression gates conservative; investigate noisy results without weakening gates to force a pass.
- Preserve raw evidence where practical, redact secrets and sensitive user data, and record model/provider metadata when available.
- Keep candidate changes small, reviewable, versioned, and reversible.
- Keep API credentials server-side and out of source control.
- Make the distinction between **passed**, **failed**, **inconclusive**, **invalid setup**, and **not applicable** explicit.

## Repository layout

```text
Pixi/
├── index.html              # Exported browser prototype
├── README.md               # Project overview and status
└── docs/
    └── ROADMAP.md          # Migration plan and milestones
```

The structure will grow as the application is migrated; avoid creating empty scaffolding until it has a clear use.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the phased plan:

1. Preserve and inspect the exported prototype.
2. Establish reproducible local tests and identify hosted-artifact dependencies.
3. Add a backend and durable database.
4. Verify experiment correctness with deterministic tests and carefully scoped live-model runs.
5. Integrate one real voice agent and collect actual traces/events/latency.
6. Deploy a small, usable product and document limitations honestly.

## Security and privacy

Do not commit `.env` files, API keys, access tokens, production call recordings, private transcripts, or personal data. Use environment variables and a secret manager for server-side credentials. Before public launch, add authentication, authorization, retention controls, redaction, rate limits, and a documented data-handling policy.

## Contributing

For now, changes should preserve the existing prototype and clearly label any new simulated behavior. Once the backend and tests exist, contributions should include tests for acceptance/rejection logic and data-loss/error cases.

## License

No license has been selected yet. Until a license is added, do not assume others have permission to reuse, modify, or redistribute this project. Choose a license before making the repository public.
