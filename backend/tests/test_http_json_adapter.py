from __future__ import annotations

import json

import httpx
import pytest

from app.adapters.http_json import HTTPJSONAgentAdapter
from app.domain.scenarios import EvidenceMode, RunVariant, Scenario


def sample_scenario() -> Scenario:
    return Scenario(
        id="pricing",
        name="Answer a pricing question",
        turns=["How much is the basic plan?"],
        assertions=[
            {
                "id": "mentions-price",
                "kind": "contains",
                "expected_text": "$20",
            }
        ],
    )


def baseline_response(**overrides: object) -> dict[str, object]:
    response: dict[str, object] = {
        "protocol_version": 2,
        "status": "completed",
        "transcript": "The basic plan costs $20 per month.",
        "latency_ms": 325,
        "tools_called": ["get_pricing"],
        "provider": "test-agent-runtime",
        "model": "support-agent-v3",
        "agent_version": "agent-base-v1",
        "variant": "baseline",
        "candidate_id": None,
    }
    response.update(overrides)
    return response


@pytest.mark.asyncio
async def test_http_bridge_sends_scenario_and_marks_valid_baseline_live() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://bridge.example.test/pixi/evaluate"
        assert request.headers["authorization"] == "Bearer server-only-secret"
        payload = json.loads(request.content)
        assert payload["protocol_version"] == 2
        assert payload["experiment"] == {"variant": "baseline", "candidate": None}
        assert payload["scenario"]["id"] == "pricing"
        return httpx.Response(200, json=baseline_response())

    adapter = HTTPJSONAgentAdapter(
        endpoint="https://bridge.example.test/pixi/evaluate",
        api_key="server-only-secret",
        transport=httpx.MockTransport(handler),
    )
    result = await adapter.execute(sample_scenario())

    assert result.evidence_mode == EvidenceMode.LIVE
    assert result.variant == RunVariant.BASELINE
    assert result.candidate_id is None
    assert result.agent_version == "agent-base-v1"
    assert result.error is None
    assert result.provider == "test-agent-runtime"
    assert result.model == "support-agent-v3"
    assert result.transcript == "The basic plan costs $20 per month."
    assert result.latency_ms == 325
    assert result.tools_called == ["get_pricing"]


@pytest.mark.asyncio
async def test_http_bridge_sends_candidate_context_and_validates_candidate_provenance() -> None:
    candidate = {
        "id": "candidate-01",
        "hypothesis": "A direct answer improves pricing responses.",
        "proposed_change": "State the basic price before describing plan details.",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["experiment"] == {"variant": "candidate", "candidate": candidate}
        return httpx.Response(
            200,
            json=baseline_response(
                transcript="The basic plan costs $20.",
                agent_version="agent-candidate-v2",
                variant="candidate",
                candidate_id="candidate-01",
            ),
        )

    adapter = HTTPJSONAgentAdapter(
        endpoint="https://bridge.example.test/evaluate",
        variant=RunVariant.CANDIDATE,
        candidate=candidate,
        transport=httpx.MockTransport(handler),
    )
    result = await adapter.execute(sample_scenario())

    assert result.variant == RunVariant.CANDIDATE
    assert result.candidate_id == "candidate-01"
    assert result.agent_version == "agent-candidate-v2"
    assert result.evidence_mode == EvidenceMode.LIVE


@pytest.mark.asyncio
async def test_http_bridge_rejects_protocol_mismatch_as_an_error() -> None:
    adapter = HTTPJSONAgentAdapter(
        endpoint="https://bridge.example.test/evaluate",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=baseline_response(protocol_version=1),
            )
        ),
    )

    with pytest.raises(RuntimeError, match="did not match protocol version 2"):
        await adapter.execute(sample_scenario())


@pytest.mark.asyncio
async def test_http_bridge_rejects_extra_provenance_fields_from_remote_payload() -> None:
    adapter = HTTPJSONAgentAdapter(
        endpoint="https://bridge.example.test/evaluate",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=baseline_response(evidence_mode="live"),
            )
        ),
    )

    with pytest.raises(RuntimeError, match="did not match protocol version 2"):
        await adapter.execute(sample_scenario())


@pytest.mark.asyncio
async def test_http_bridge_rejects_variant_or_candidate_mismatch() -> None:
    adapter = HTTPJSONAgentAdapter(
        endpoint="https://bridge.example.test/evaluate",
        variant=RunVariant.CANDIDATE,
        candidate={
            "id": "candidate-01",
            "hypothesis": "Improve pricing response.",
            "proposed_change": "Answer with the price first.",
        },
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=baseline_response(),
            )
        ),
    )

    with pytest.raises(RuntimeError, match="did not match the requested experiment variant"):
        await adapter.execute(sample_scenario())


@pytest.mark.asyncio
async def test_http_bridge_rejects_non_success_status_without_exposing_body() -> None:
    adapter = HTTPJSONAgentAdapter(
        endpoint="https://bridge.example.test/evaluate",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(502, text="sensitive upstream error details")
        ),
    )

    with pytest.raises(RuntimeError, match="HTTP 502") as error:
        await adapter.execute(sample_scenario())
    assert "sensitive upstream error" not in str(error.value)


@pytest.mark.asyncio
async def test_http_bridge_does_not_follow_redirects() -> None:
    adapter = HTTPJSONAgentAdapter(
        endpoint="https://bridge.example.test/evaluate",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(307, headers={"Location": "https://other.example.test/"})
        ),
    )

    with pytest.raises(RuntimeError, match="redirects are disabled"):
        await adapter.execute(sample_scenario())


def test_http_bridge_requires_https_outside_local_development() -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        HTTPJSONAgentAdapter(endpoint="http://bridge.example.test/evaluate")


def test_http_bridge_allows_loopback_http_only_when_explicitly_enabled() -> None:
    adapter = HTTPJSONAgentAdapter(
        endpoint="http://127.0.0.1:8765/evaluate",
        allow_insecure_localhost=True,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=baseline_response())
        ),
    )
    assert adapter.endpoint == "http://127.0.0.1:8765/evaluate"


@pytest.mark.parametrize(
    "endpoint",
    [
        "not-a-url",
        "ftp://bridge.example.test/evaluate",
        "https://user:password@bridge.example.test/evaluate",
        "https://bridge.example.test/evaluate#fragment",
    ],
)
def test_http_bridge_rejects_malformed_or_credential_bearing_urls(endpoint: str) -> None:
    with pytest.raises(ValueError):
        HTTPJSONAgentAdapter(endpoint=endpoint)


@pytest.mark.parametrize("timeout", [0, -1, 30.01, 100])
def test_http_bridge_timeout_is_bounded(timeout: float) -> None:
    with pytest.raises(ValueError, match="between 0.1 and 30"):
        HTTPJSONAgentAdapter(
            endpoint="https://bridge.example.test/evaluate",
            timeout_seconds=timeout,
        )


def test_candidate_variant_requires_candidate_context() -> None:
    with pytest.raises(ValueError, match="requires a candidate proposal"):
        HTTPJSONAgentAdapter(
            endpoint="https://bridge.example.test/evaluate",
            variant=RunVariant.CANDIDATE,
        )
