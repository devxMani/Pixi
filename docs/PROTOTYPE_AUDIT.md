# Prototype audit notes

**Scope:** a preliminary source inventory of `index.html`, the exported browser prototype. This is not a complete security review or production-readiness assessment.

## Confirmed observations

- The prototype is a single HTML document with embedded CSS and bundled JavaScript.
- It contains the Miso conversational demo and Ready, Test, Bench, Secure, Build, Monitor, and Improve console areas.
- Browser-local preferences and prototype state use `localStorage`; this is not durable multi-user storage.
- The page contains a branch for a Claude-hosted sample capability. That capability is tied to the artifact's original runtime and is not guaranteed to exist when the HTML is served locally.
- The prototype itself distinguishes implemented behavior from simulated behavior. In particular, the default agent, rule-based diagnosis/candidate generation, noise/accent variants, call log, and "marking live" are not evidence of a real external voice-agent integration.
- Branding strings have been normalized to **Pixi**; the interaction model and visual layout have otherwise been preserved.

## Engineering implications

1. Keep the HTML as a baseline while its behavior is inventoried and covered by tests.
2. Do not rely on artifact-specific capabilities for the product backend.
3. Do not treat browser state or demo history as the source of truth.
4. Ensure the UI displays an unmistakable evidence-mode marker for every scenario/run.
5. Use the new backend adapter boundary for provider integrations; provider credentials belong server-side.
6. Do not add customer transcripts or audio to fixtures, CI logs, or Git history.

## Security review still required

- Review every external script/style/font dependency and pin or self-host dependencies where practical.
- Inspect all network requests and provider capability calls in a local browser.
- Review dynamic HTML insertion, URL handling, user-generated content, and message rendering for injection risks.
- Review data retention, transcript redaction, audio handling, and access controls before connecting real customer systems.
- Use automated secret scanning and a full manual audit before treating this repository as production-ready.

## Current conclusion

The prototype is useful as a UI/reference artifact, but it is not yet a production web application. A preliminary string scan found no obvious API-key-shaped value; that limited scan is not proof that the file or repository is secret-free.
