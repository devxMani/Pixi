# Pixi

**A reliability workspace for voice agents. Find failures, reproduce them, and verify fixes against regression suites.**

Pixi is an early-stage project exploring a closed-loop testing and reliability workflow for voice agents: scenario execution, evidence-backed failure analysis, small reversible candidate changes, and conservative regression-gated decisions.

> **Status: early prototype + first API scaffold.** The browser prototype remains in `index.html`. The API currently provides a testable evaluation decision policy; it does not yet connect to a real voice agent or persist runs. Never treat simulated runs as live-provider evidence.

## Product direction
The MVP is for engineers building voice agents who need to investigate interruptions, tool failures, latency, response quality, and safety regressions. The core promise is: **know what broke, reproduce it, and prove a fix does not regress the agent.**

See [Product specification](docs/PRODUCT_SPEC.md), [Architecture](docs/ARCHITECTURE.md), [Prototype audit](docs/PROTOTYPE_AUDIT.md), [Roadmap](ROADMAP.md), [Engineering guide](docs/ENGINEERING_GUIDE.md), and [Contributing](CONTRIBUTING.md).

## Current repository
- `index.html` — preserved exported browser prototype.
- `backend/app/domain/evaluation.py` — pure conservative experiment decision policy.
- `backend/app/domain/scenarios.py` and `scenario_runner.py` — validated scenario/assertion contracts and conservative scenario result classification.
- `backend/app/adapters/` — provider-neutral adapter protocol plus a fixture adapter explicitly labeled simulated.
- `backend/app/main.py` — minimal FastAPI health and experiment-decision endpoints.
- `backend/tests/` — policy, scenario, and API tests.
- `.github/workflows/backend-ci.yml` — backend tests and linting on pushes/PRs.
- `docs/` — product and engineering decisions.

## Run the prototype
Open `index.html` in a modern browser. It may depend on hosted-artifact features that do not work outside that runtime. Browser-local state is not durable production persistence.

## Run the API
Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

- Health: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs
- Tests: `cd backend && pytest`
- Lint: `cd backend && ruff check app tests`

The decision API evaluates supplied checks. The domain layer now defines a provider-neutral scenario execution contract and a deterministic fixture adapter, but there is no real voice-agent adapter, run persistence, or experiment management yet.

## Evaluation safety contract
Pixi distinguishes `passed`, `failed`, `inconclusive`, `invalid_setup`, and `not_applicable`. A missing observation, provider error, incomplete regression suite, empty regression suite, or invalid precondition cannot be counted as a pass. Critical safety regressions block acceptance.

## Near-term build plan
1. Inventory the HTML prototype and preserve its current behavior.
2. Stabilize testable evaluation rules and CI.
3. Add typed persistence models and database migrations.
4. Add a provider-neutral adapter contract and a fake adapter for integration tests.
5. Choose and connect one real voice-agent runtime based on the agent to evaluate.
6. Integrate the UI with durable run/evidence APIs and add auth/privacy boundaries before customer data is stored.

## Security
Never commit real secrets, call recordings, or private transcripts. Provider credentials must remain server-side. The API scaffold is not production-secure: authentication, project authorization, rate limiting, retention controls, and deployment hardening are not implemented yet.

## License
No license has been selected. Until one is added, do not assume others have permission to reuse or redistribute the code.
