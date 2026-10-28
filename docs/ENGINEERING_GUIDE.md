# Engineering guide

## Workflow
- Keep `main` releasable; use short feature branches and pull requests for substantial changes.
- Make the smallest verifiable change.
- Add a test for every outcome/decision rule and every discovered bug.
- Do not refactor the exported baseline blindly; inventory behavior first.
- Prefer clear typed models and explicit status enums over implicit state.
- Document trade-offs when a provider or runtime cannot expose a required event.

## Quality gates
1. Format/lint.
2. Unit tests for evaluation policy.
3. API tests for validation, authorization, persistence, and failure handling.
4. Integration tests with fake adapters in normal CI.
5. Live-provider tests only on explicit opt-in, with bounded duration/call count and spend limits.
6. Run `npm run typecheck`, `npm run lint`, and `npm run build` from `web/`; manually accept the main Next.js workflows and keep the legacy HTML prototype available for comparison.

## Data and secrets
- Never put provider keys in the browser, repository, screenshots, issue descriptions, or ordinary logs.
- Keep `.env` local and ignored; commit only `.env.example` with placeholder values.
- Do not use real customer audio/transcripts in tests or commits.
- Redact payloads before persistence where feasible.
- Never treat a fixture or fake adapter as live evidence.

## Agent integration boundary
Read [the HTTP agent bridge contract](AGENT_BRIDGE.md) before configuring `PIXI_AGENT_ENDPOINT` or writing a provider adapter. The built-in bridge is a strict protocol boundary; it is not proof that a particular vendor has been integrated. Keep credentials server-side, disable redirects, cap timeouts, and treat transport/protocol failures as inconclusive.

## Current application structure
- `backend/` owns the FastAPI API, typed evaluation contracts, adapter protocol, persistence models, and Alembic migrations.
- `web/` owns the Next.js App Router/TypeScript UI and its same-origin API proxy.
- `index.html` and `console.html` are retained as historical/reference implementations; new workspace features belong in `web/` unless there is a specific reason to maintain the legacy page.
- The API and proxy must remain development-only until real authentication and project-level authorization are implemented. Do not enable a public deployment by changing only an environment variable.

## Next integration milestone
Choose the actual voice-agent runtime and implement/verify its bridge. The current HTTP bridge describes a contract; mocked tests do not establish a real external-agent integration. Live integration must be isolated, opt-in, bounded by time/spend, and return genuinely observed versioned evidence.
