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
6. Manual acceptance check against the browser prototype during UI migration.

## Data and secrets
- Never put provider keys in the browser, repository, screenshots, issue descriptions, or ordinary logs.
- Keep `.env` local and ignored; commit only `.env.example` with placeholder values.
- Do not use real customer audio/transcripts in tests or commits.
- Redact payloads before persistence where feasible.
- Never treat a fixture or fake adapter as live evidence.

## Proposed first implementation
Add a minimal Python/FastAPI service with an isolated evaluation-policy module and tests before adding the database. The first module should make pass/fail/inconclusive rules independent of HTTP or provider SDKs. Then add PostgreSQL with migrations when the data model is defined. Do not build a UI rewrite until the core result contract is tested.
