"""Deterministic fixture adapter for tests and demos; never reports live evidence."""
from __future__ import annotations

from app.domain.scenarios import AgentObservation, EvidenceMode, RunVariant, Scenario


class FixtureAgentAdapter:
    name = "fixture"
    evidence_mode = EvidenceMode.SIMULATED
    variant = RunVariant.SIMULATED
    candidate_id: str | None = None

    def __init__(
        self,
        *,
        transcript: str = "",
        latency_ms: float | None = None,
        tools_called: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        self._transcript = transcript
        self._latency_ms = latency_ms
        self._tools_called = tools_called or []
        self._error = error

    async def execute(self, scenario: Scenario) -> AgentObservation:
        """Return configured fixture evidence; the result is always explicitly simulated."""
        del scenario  # fixture output is configured by the test, not a real agent runtime
        return AgentObservation(
            transcript=self._transcript,
            latency_ms=self._latency_ms,
            tools_called=self._tools_called,
            error=self._error,
            evidence_mode=EvidenceMode.SIMULATED,
            provider=self.name,
        )
