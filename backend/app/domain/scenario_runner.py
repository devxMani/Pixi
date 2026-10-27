"""Orchestrate one scenario through an adapter and classify its evidence."""
from __future__ import annotations

from app.adapters.base import AgentAdapter
from app.domain.scenarios import (
    AgentObservation,
    Scenario,
    ScenarioResult,
    ScenarioStatus,
    evaluate_scenario,
)


async def run_scenario(adapter: AgentAdapter, scenario: Scenario) -> ScenarioResult:
    """Run one scenario; exceptions and missing required evidence are inconclusive."""
    try:
        observation = await adapter.execute(scenario)
        if observation.evidence_mode != adapter.evidence_mode:
            observation = AgentObservation(
                error="Adapter evidence mode did not match the adapter declaration.",
                evidence_mode=adapter.evidence_mode,
                provider=adapter.name,
            )
    except Exception as exc:  # noqa: BLE001 - adapter failures must remain inconclusive evidence
        observation = AgentObservation(
            error=f"{type(exc).__name__}: {exc}",
            evidence_mode=adapter.evidence_mode,
            provider=adapter.name,
        )

    checks = evaluate_scenario(scenario, observation)
    if any(check.passed is None or check.error for check in checks):
        status = ScenarioStatus.INCONCLUSIVE
    elif any(check.passed is False for check in checks):
        status = ScenarioStatus.FAILED
    else:
        status = ScenarioStatus.PASSED

    return ScenarioResult(
        scenario_id=scenario.id,
        adapter_name=adapter.name,
        evidence_mode=adapter.evidence_mode,
        status=status,
        checks=checks,
        observation=observation,
    )
