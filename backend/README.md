# Pixi API (early scaffold)

## Status
This is the first backend foundation, not a complete product backend. It implements a pure, testable evaluation decision policy and exposes it through FastAPI. It does not yet connect to an agent provider or store runs in a database.

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

The API's evaluation endpoint receives already-evaluated checks; it does not itself call an agent. Provider adapters, run persistence, authentication, and project isolation remain future work.
