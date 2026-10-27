# Pixi API (early scaffold)

## Status
This is the first backend foundation, not a complete product backend. It implements a pure, testable experiment decision policy, scenario/assertion contracts, a conservative scenario runner, and a deterministic fixture adapter. It does not yet connect to a real agent provider or store runs in a database.

## Run locally
From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Open the interactive API docs at `http://127.0.0.1:8000/docs`.

## Run tests
```bash
pytest
```

The evaluation endpoint receives already-evaluated checks; the scenario runner can execute only adapters explicitly implemented in code, and the included fixture adapter is simulated. No real agent provider integration, run persistence, authentication, or project isolation exists yet.
