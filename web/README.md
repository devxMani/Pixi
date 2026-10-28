# Pixi Web

The primary Reliability Workspace is a Next.js App Router application built with React and strict TypeScript. The legacy HTML console remains at the repository root for reference, but new workspace UI work should go here.

## Local development

Start the FastAPI backend in another terminal first:

```bash
cd ../backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export APP_ENV=development
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Then from this directory:

```bash
npm install
npm run dev
```

Open http://localhost:3000. By default the same-origin proxy forwards API requests to `http://127.0.0.1:8000/api/v1`. Set `PIXI_API_BASE_URL` in `.env.local` only when your local backend lives elsewhere.

## Checks

```bash
npm run typecheck
npm run lint
npm run build
```

GitHub Actions runs these checks on changes under `web/`.

## Important safety boundary

This is a local engineering environment, not a public deployment. The FastAPI API is guarded by `APP_ENV=development`, and the Next.js API proxy refuses all requests in production mode. Do not weaken either guard or expose the dev server on a public network. Authentication, project ownership/authorization, request rate limits, transcript redaction/retention, and production deployment hardening remain required before enabling remote users.

## Layout

- `app/page.tsx`: workspace entry.
- `app/workspace.tsx`: interactive screens and workflows.
- `app/api/pixi/[...path]/route.ts`: development-only same-origin API proxy.
- `lib/api.ts`: typed API client.
- `lib/types.ts`: frontend DTO types.
- `app/globals.css`: responsive visual system.
