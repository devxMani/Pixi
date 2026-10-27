"""Scenario and observation contracts for evidence-backed agent evaluations."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.evaluation import CheckResult


class EvidenceMode(StrEnum):
    SIMULATED = "simulated"
    LIVE = "live"


class RunVariant(StrEnum):
    SIMULATED = "simulated"
    BASELINE = "baseline"
    CANDIDATE = "candidate"


class AssertionKind(StrEnum):
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MAX_LATENCY_MS = "max_latency_ms"
    TOOL_CALLED = "tool_called"
    TOOL_NOT_CALLED = "tool_not_called"


class ScenarioAssertion(BaseModel):
    id: str = Field(min_length=1)
    kind: AssertionKind
    expected_text: str | None = None
    threshold_ms: float | None = Field(default=None, ge=0)
    tool_name: str | None = None
    critical: bool = False

    @model_validator(mode="after")
    def validate_required_argument(self) -> ScenarioAssertion:
        if (
            self.kind in (AssertionKind.CONTAINS, AssertionKind.NOT_CONTAINS)
            and (not self.expected_text or not self.expected_text.strip())
        ):
            raise ValueError("expected_text is required for text assertions")
        if self.kind == AssertionKind.MAX_LATENCY_MS and self.threshold_ms is None:
            raise ValueError("threshold_ms is required for latency assertions")
        if (
            self.kind in (AssertionKind.TOOL_CALLED, AssertionKind.TOOL_NOT_CALLED)
            and (not self.tool_name or not self.tool_name.strip())
        ):
            raise ValueError("tool_name is required for tool assertions")
        return self


class Scenario(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    turns: list[str] = Field(min_length=1)
    assertions: list[ScenarioAssertion] = Field(min_length=1)


class AgentObservation(BaseModel):
    """Sanitized evidence returned by an adapter; raw audio is intentionally absent."""

    transcript: str = ""
    latency_ms: float | None = Field(default=None, ge=0)
    tools_called: list[str] = Field(default_factory=list)
    error: str | None = None
    evidence_mode: EvidenceMode = EvidenceMode.SIMULATED
    provider: str | None = None
    model: str | None = None
    agent_version: str | None = None
    variant: RunVariant = RunVariant.SIMULATED
    candidate_id: str | None = None


class ScenarioStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    adapter_name: str
    evidence_mode: EvidenceMode
    status: ScenarioStatus
    checks: tuple[CheckResult, ...]
    observation: AgentObservation


def evaluate_scenario(scenario: Scenario, observation: AgentObservation) -> tuple[CheckResult, ...]:
    """Evaluate explicitly configured assertions without inferring missing evidence."""
    if observation.error:
        return tuple(
            CheckResult(name=assertion.id, passed=None, error=observation.error)
            for assertion in scenario.assertions
        )

    transcript = observation.transcript.casefold()
    called_tools = set(observation.tools_called)
    results: list[CheckResult] = []
    for assertion in scenario.assertions:
        passed: bool | None
        error: str | None = None
        if assertion.kind == AssertionKind.CONTAINS:
            passed = assertion.expected_text.casefold() in transcript
        elif assertion.kind == AssertionKind.NOT_CONTAINS:
            passed = assertion.expected_text.casefold() not in transcript
        elif assertion.kind == AssertionKind.MAX_LATENCY_MS:
            if observation.latency_ms is None:
                passed = None
                error = "Latency evidence is unavailable."
            else:
                passed = observation.latency_ms <= assertion.threshold_ms
        elif assertion.kind == AssertionKind.TOOL_CALLED:
            passed = assertion.tool_name in called_tools
        elif assertion.kind == AssertionKind.TOOL_NOT_CALLED:
            passed = assertion.tool_name not in called_tools
        else:  # pragma: no cover - exhaustive guard for future enum additions
            passed = None
            error = f"Unsupported assertion kind: {assertion.kind}"
        results.append(CheckResult(name=assertion.id, passed=passed, error=error))
    return tuple(results)
