"""Provider-neutral contract for scenario execution."""
from __future__ import annotations

from typing import Protocol

from app.domain.scenarios import AgentObservation, EvidenceMode, Scenario


class AgentAdapter(Protocol):
    """An adapter executes a complete scenario against an agent runtime.

    Real adapters must report `LIVE` only when the response and evidence came from an
    actual external-agent execution. Fixtures and canned responses must report `SIMULATED`.
    """

    name: str
    evidence_mode: EvidenceMode

    async def execute(self, scenario: Scenario) -> AgentObservation:
        """Execute the scenario and return transcript, metrics, tool events, or an error."""
        ...
