# Pixi API

The API includes the tested evaluation policy, scenario/assertion contracts, provider-neutral adapter protocol, SQLAlchemy persistence, and a browser workspace with a persisted candidate review flow. Candidate-gate runs are stamped simulated, and release approval is rejected without passing live-agent evidence.

## Run locally

Requires Python 3.11+.

1. Create and activate a virtual environment.
2. Install the project with development dependencies using pip install -e '.[dev]'.
3. Set APP_ENV=development in your local shell.
4. Run alembic upgrade head.
5. Run uvicorn app.main:app --reload.

Open http://127.0.0.1:8000/console.html for the Reliability Workspace, http://127.0.0.1:8000 for the preserved Miso prototype, and http://127.0.0.1:8000/docs for interactive API documentation.

## Demonstration workflow

1. Create a project in the workspace.
2. Define a scenario with caller turns and one or more assertions.
3. Submit a fixture transcript, latency, and tool-call list.
4. Inspect the saved run, observation, assertion checks, and evidence mode.

Important: this is a simulation workflow. The fixture adapter does not invoke a model or external agent. Never enter customer secrets or private transcripts.

## Persistence and environment

- Default local database: sqlite:///./pixi.db.
- PostgreSQL is supported through DATABASE_URL and the psycopg driver.
- Apply schema changes with Alembic; migrations are in the migrations directory.
- Every /api/v1 route is disabled unless APP_ENV=development. Authentication and project authorization must be implemented before deploying or storing real data.

## Checks

- pytest
- ruff check app tests
- The CI workflow validates the schema migration against SQLite and syntax-checks both browser interfaces.

No real voice-agent integration or production-ready authentication/retention controls exist yet.
