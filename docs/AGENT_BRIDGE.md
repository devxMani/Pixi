# Pixi HTTP agent bridge contract

This provider-neutral bridge is the integration boundary between Pixi and a voice-agent runtime. It is **not** a built-in or verified integration with any named vendor. Configure a server-side endpoint you control, or implement a wrapper for the actual runtime, that follows protocol version 2.

## Request contract

Pixi sends a JSON POST to `PIXI_AGENT_ENDPOINT` for each scenario. A baseline request has no candidate attached:

```json
{
  "protocol_version": 2,
  "scenario": {
    "id": "pricing-basic",
    "name": "Answer a pricing question",
    "turns": ["How much does the basic plan cost?"],
    "assertions": [
      {
        "id": "mentions-price",
        "kind": "contains",
        "expected_text": "$20",
        "critical": false
      }
    ]
  },
  "experiment": {
    "variant": "baseline",
    "candidate": null
  }
}
```

A candidate request uses the same scenario field and sets the experiment context to:

```json
{
  "variant": "candidate",
  "candidate": {
    "id": "candidate-record-id",
    "hypothesis": "A direct answer improves pricing responses.",
    "proposed_change": "State the basic plan price before the plan details."
  }
}
```

Candidate text is untrusted proposal metadata, **not executable code**. The bridge must use its own supported mechanisms to test the candidate in an isolated, non-production environment. It must not apply a candidate to production or simply echo the proposal as if it had been applied. If it cannot create or select a candidate version safely, it should reject the request or return an error.

## Successful response contract

For a baseline request:

```json
{
  "protocol_version": 2,
  "status": "completed",
  "transcript": "The basic plan costs $20 per month.",
  "latency_ms": 620,
  "tools_called": ["get_pricing"],
  "provider": "your-runtime",
  "model": "support-agent-model",
  "agent_version": "agent-config-or-build-immutable-id",
  "variant": "baseline",
  "candidate_id": null,
  "voice_trace": {
    "status": "completed",
    "error": null,
    "input_mode": "text",
    "latency_basis": "text_input_to_completed_response",
    "agent_version": "agent-config-or-build-immutable-id",
    "candidate_id": null,
    "measured_turn_count": 1,
    "scenario_elapsed_ms": 625,
    "turns": [
      {
        "user_input": "How much does the basic plan cost?",
        "assistant_output": "The basic plan costs $20 per month.",
        "tools": [
          {
            "name": "get_pricing",
            "arguments": {"plan": "basic"},
            "output": "$20 per month",
            "latency_ms": 8.5,
            "success": true,
            "error": null
          }
        ],
        "latency": {
          "stt_processing_ms": null,
          "eot_latency_ms": null,
          "llm_ttft_ms": 140,
          "tts_ttfb_ms": 90,
          "e2e_ms": 325
        },
        "interruption": {
          "interrupted": false,
          "overlapping_speech": false,
          "false_interruption": false,
          "detection_delay_ms": null,
          "agent_speech_duration_ms": null,
          "recovered": false
        },
        "interrupted": false,
        "status": "completed",
        "error": null
      }
    ]
  }
}
```

The `voice_trace` object is optional for generic protocol-v2 bridges. When supplied, it must be structured per-turn evidence with the same `agent_version` and `candidate_id` as the response envelope; `measured_turn_count` must equal the number of turns. Pixi validates and persists it, exposes it in run inspection, and includes it in JSON backups. Null STT/endpointing/interruption metrics mean the bridge did not measure them, not that the metrics were zero. For scripted-text LiveKit runs, use `input_mode=text` and `latency_basis=text_input_to_completed_response`; do not label these timings as microphone-to-audio latency.

For a candidate request, `variant` must be `candidate`, `candidate_id` must exactly match the requested candidate record ID, and `agent_version` must identify the actual immutable candidate build/configuration. The same candidate version must be returned for its target and all regression scenarios in an experiment.

Required: `protocol_version=2`, `status=completed`, non-empty `agent_version`, matching `variant`, and matching `candidate_id`. `transcript` must be a string. `latency_ms` may be `null` when the bridge cannot measure meaningful agent latency. Tool names must be events actually observed in the trace. `provider` and `model` are optional descriptive metadata. Unknown fields are rejected to make schema drift visible.

## Configuration

Set these variables on the Pixi server (never in the browser):

- `PIXI_AGENT_ENDPOINT`: fixed bridge URL. HTTPS is required except HTTP on localhost/loopback when `APP_ENV=development`.
- `PIXI_AGENT_API_KEY`: optional bearer credential. Keep the real value in ignored `.env` or a managed secrets store.
- `PIXI_AGENT_TIMEOUT_SECONDS`: bounded request timeout from 0.1 to 30 seconds; defaults to 15.

Redirects are disabled; configure the final endpoint directly. The URL is operator configuration rather than user input. Only point it at a service you trust and apply appropriate outbound network policy.

## Evidence and candidate gate

A configured bridge is a trust boundary; a response field alone cannot prove that the bridge truly ran the named build. Pixi records its reported immutable `agent_version`, requested variant, and candidate ID so reviewers can inspect what the trusted bridge claims it executed.

The live candidate gate is `POST /api/v1/candidates/{candidate_id}/evaluate-runs`. It requires:
1. A recorded live **baseline** run for the candidate's target scenario that failed.
2. A recorded live **candidate** run for that same target scenario that belongs to this candidate.
3. A live candidate-variant regression run for **every other saved scenario in the project**. Until Pixi has named/tagged regression suites, all non-target project scenarios form the required suite.
4. The same candidate ID and agent version across the candidate target and every regression run, and a candidate version different from the baseline.
5. Passing target and regression checks. Any critical regression blocks approval.

The endpoint rejects a partial regression suite, duplicate scenario coverage, cross-project evidence, fixture runs, mismatched candidate IDs, missing version metadata, and mixed candidate versions. A new scenario added to the project must be evaluated against the candidate before the gate can pass. This is conservative by design; named or tagged regression suites are a future improvement.

The gate reads persisted run checks, not caller-submitted booleans. It records the referenced run IDs and check snapshots. Human review is still required; Pixi does not deploy or mutate the agent. Simulated runs cannot satisfy the live gate.

## Not yet standardized

The contract captures text transcript, a latency measurement, tool-call names, build/version ID, and variant provenance. It does not yet standardize audio sample transport, timestamps for every turn, barge-in/interruption, VAD/endpointing traces, time-to-first-audio, or provider-specific cost details. These need runtime-specific extensions and tests.

## Production checklist

Before using real/customer traffic, add authentication and project authorization to Pixi, enforce egress/network policy, use managed secrets, add transcript redaction/retention controls, cap call volume and cost, and complete a security review. Pixi's current API is development-only until authentication and project authorization are implemented.
