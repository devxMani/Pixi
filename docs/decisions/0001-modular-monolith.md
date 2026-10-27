# ADR 0001: Start with a modular monolith

- **Status:** Accepted for MVP
- **Date:** 2026-10-28

## Context
Pixi is a prototype with no verified production workload yet. The central risks are correctness of evaluation decisions, actual agent integration, evidence integrity, and safe handling of sensitive conversation data.

## Decision
Start with a single API service, one frontend, and PostgreSQL. Keep domain modules separated in code. Do not introduce microservices, Kubernetes, or a queue until measured usage or long-running session requirements justify them.

## Consequences
- Lower operational complexity and faster feedback.
- A single deployment can be tested end-to-end.
- Explicit module boundaries preserve a path to extraction later.
- Long-running agent sessions may need a worker when a real adapter is integrated.
