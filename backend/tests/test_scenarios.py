import pytest
from pydantic import ValidationError

from app.adapters.fake import FixtureAgentAdapter
from app.domain.scenario_runner import run_scenario
from app.domain.scenarios import (
    AssertionKind,
    EvidenceMode,
    Scenario,
    ScenarioAssertion,
    ScenarioStatus,
)


def make_scenario() -> Scenario:
    return Scenario(
        id="pricing-basic",
        name="Answer pricing question",
        turns=["How much does the basic plan cost?"],
        assertions=[
            ScenarioAssertion(id="mentions-price", kind=AssertionKind.CONTAINS, expected_text="$20"),
            ScenarioAssertion(id="no-secret", kind=AssertionKind.NOT_CONTAINS, expected_text="api key"),
            ScenarioAssertion(id="latency-budget", kind=AssertionKind.MAX_LATENCY_MS, threshold_ms=1500),
            ScenarioAssertion(id="pricing-tool", kind=AssertionKind.TOOL_CALLED, tool_name="get_pricing"),
        ],
    )


@pytest.mark.asyncio
async def test_fixture_scenario_passes_but_is_never_live_evidence():
    result = await run_scenario(
        FixtureAgentAdapter(
            transcript="The basic plan costs $20 per month.",
            latency_ms=820,
            tools_called=["get_pricing"],
        ),
        make_scenario(),
    )
    assert result.status == ScenarioStatus.PASSED
    assert result.evidence_mode == EvidenceMode.SIMULATED
    assert result.observation.evidence_mode == EvidenceMode.SIMULATED


@pytest.mark.asyncio
async def test_failed_assertion_fails_scenario():
    result = await run_scenario(
        FixtureAgentAdapter(transcript="It costs $30.", latency_ms=200, tools_called=[]),
        make_scenario(),
    )
    assert result.status == ScenarioStatus.FAILED
    assert any(check.passed is False for check in result.checks)


@pytest.mark.asyncio
async def test_missing_latency_makes_scenario_inconclusive():
    result = await run_scenario(
        FixtureAgentAdapter(transcript="It costs $20.", tools_called=["get_pricing"]),
        make_scenario(),
    )
    assert result.status == ScenarioStatus.INCONCLUSIVE
    assert any(check.error == "Latency evidence is unavailable." for check in result.checks)


@pytest.mark.asyncio
async def test_provider_error_is_inconclusive():
    result = await run_scenario(
        FixtureAgentAdapter(error="provider timeout"),
        make_scenario(),
    )
    assert result.status == ScenarioStatus.INCONCLUSIVE
    assert all(check.passed is None for check in result.checks)


def test_assertion_schema_rejects_missing_expected_text():
    with pytest.raises(ValidationError):
        ScenarioAssertion(id="must-have-price", kind=AssertionKind.CONTAINS)
