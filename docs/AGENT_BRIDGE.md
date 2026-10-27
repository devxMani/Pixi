# Pixi HTTP agent bridge contract

This is a provider-neutral integration boundary, not a claim that Pixi already integrates with a particular vendor. Configure a server-side endpoint you control, or write a small adapter service for the actual voice-agent runtime, that implements this protocol.

## Request

Pixi sends one JSON POST request per scenario to `PIXI_AGENT_ENDPOINT`.

```json
{
  "protocol_version": 1,
  "scenario": {
    "id": "pricing-basic",
    "name": "Answer a pricing question",
    "turns": ["How much does the basic plan cost?"],
    "assertions": [
      {
        "id": "mentions-price",
        "kind": "contains",
        "expected_text": "$20",
        "threshold_ms": null,
        "tool_name": null
      }
    ]
  }
}
```

The bridge must execute the provided scenario against an actual configured agent and return its observed output. It must not just echo the prompt or manufacture transcript/tool/latency values. For multi-turn or real audio interaction, the bridge should orchestrate the agent's supported session API and report what it actually observed. If the runtime cannot expose a field, return `null` where allowed instead of guessing.

## Successful response

```json
{
  "protocol_version": 1,
  "status": "completed",
  "transcript": "The basic plan costs $20 per month.",
  "latency_ms": 620,
  "tools_called": ["get_pricing"],
  "provider": "your-runtime",
  "model": "agent-version-abc"
}
```

Required: `protocol_version` must be `1`, `status` must be `completed`, and `transcript` must be a string. `latency_ms` may be `null` when the bridge cannot measure meaningful agent latency. Tool names must be the events actually observed in the agent trace. `provider` and `model` are optional metadata, not authentication signals. Unknown response fields are rejected so schema drift is visible.

## Configuration

Set these variables on the Pixi server (never in the browser):

- `PIXI_AGENT_ENDPOINT`: fixed endpoint URL. HTTPS is required except HTTP on localhost/loopback when `APP_ENV=development`.
- `PIXI_AGENT_API_KEY`: optional bearer credential. Store the real value in `.env` or a managed secret store, never commit it.
- `PIXI_AGENT_TIMEOUT_SECONDS`: bounded request timeout from 0.1 to 30 seconds; defaults to 15.

Redirects are disabled. Configure the final endpoint directly. The URL is operator configuration rather than user input. Only point it at a service you trust.

## Failure and provenance semantics

Pixi will mark a valid response obtained through this configured HTTP bridge as `live` evidence. A timeout, HTTP error, redirect, invalid JSON, or incompatible response becomes an inconclusive run; it must never be scored as a pass. A provider name in a payload does not prove provenance: the operator-configured endpoint is the trust boundary, so the bridge itself must be honest and authenticated appropriately.

The current protocol captures transcript, reported latency, and tool-call names. It does **not** yet standardize audio samples, timestamps for every turn, barge-in/interruption events, VAD/endpointing traces, or time-to-first-audio. Those require a runtime-specific adapter extension.

## Production checklist

Before using real/customer traffic, add authentication and project authorization to Pixi, enforce egress/network policy for the configured URL, use a managed secrets provider, add transcript redaction/retention controls, cap call volume/cost, and complete a security review. Pixi's current API is development-only until authentication and project authorization are implemented.
