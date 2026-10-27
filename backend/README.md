# Pixi API

## Status

The API includes a tested evaluation policy, scenario/assertion contracts, a conservative scenario runner, an explicitly simulated fixture adapter, and a persisted development workflow for projects, scenarios, demo runs, observations, and assertion results.

Important: the demo-runs endpoint uses caller-provided fixture output; it does not call an external agent. All demo evidence is marked simulated. API routes are blocked unless APP_ENV=development, because authentication and project-level authorization have not been implemented. Do not expose this API to the public internet or store customer conversations in it yet.

## Run locally

Requires Python 3.11+.

1. Create and activate a virtual environment.
2. Install the project with development dependencies.
3. Set APP_ENV=development for your local shell.
4. Run alembic upgrade head.
5. Run uvicorn app.main:app --reload.

Open the API docs at http://127.0.0.1:8000/docs.

## Demo workflow

1. POST /api/v1/projects with {"name":"Local demo"}.
2. POST /api/v1/projects/{project_id}/scenarios with a name, user turns, and assertions.
3. POST /api/v1/projects/{project_id}/scenarios/{scenario_id}/demo-runs with a fixture transcript, latency, tool names, or an explicit fixture error.
4. GET /api/v1/runs/{run_id} to inspect persisted observations and check results.

The result is always labeled simulated. The current adapter contract is ready for an actual provider implementation, but none is connected.

## Database configuration

- Default local database: sqlite:///./pixi.db.
- PostgreSQL example: set DATABASE_URL to a postgresql+psycopg URL such as postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME.
- Apply schema changes with Alembic; migrations are in the migrations directory.

## Tests

- pytest
- ruff check app tests

The current foundation has no real voice-agent integration, authentication, project authorization, retention/redaction controls, or production deployment hardening.
