# Contributing to Pixi

Thanks for helping make voice-agent evaluations more reproducible.

## Before changing code
Read the [product spec](docs/PRODUCT_SPEC.md), [architecture](docs/ARCHITECTURE.md), and [roadmap](ROADMAP.md). The checked-in HTML is a prototype baseline; do not delete or replace it before behavior has been inventoried.

## Development rules
- Keep simulated data visibly labeled.
- Add deterministic tests for evaluation and acceptance logic.
- Missing evidence, incomplete regression runs, provider errors, and malformed outputs must never be counted as passes.
- Keep candidate changes small and reversible.
- Never include API keys, customer transcripts, raw audio, or personal information in commits.
- Describe what was tested and what was not tested in PRs.

## Pull requests
Include the problem, approach, test commands/results, limitations, and screenshots for user-facing changes. Live-provider testing must be opt-in and include clear budget/consent boundaries.
