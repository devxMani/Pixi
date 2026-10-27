"""Validated request schemas for the development API."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.scenarios import ScenarioAssertion


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def require_nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name cannot be blank.")
        return value.strip()


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    turns: list[str] = Field(min_length=1, max_length=100)
    assertions: list[ScenarioAssertion] = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def require_nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Scenario name cannot be blank.")
        return value.strip()

    @field_validator("turns")
    @classmethod
    def require_nonblank_turns(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("Scenario turns cannot be blank.")
        return cleaned


class FixtureObservationInput(BaseModel):
    """Caller-supplied fixture output, used only by the clearly simulated demo route."""

    transcript: str = Field(default="", max_length=100_000)
    latency_ms: float | None = Field(default=None, ge=0)
    tools_called: list[str] = Field(default_factory=list, max_length=100)
    error: str | None = Field(default=None, max_length=1000)


class CheckInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    passed: bool | None
    critical: bool = False
    error: str | None = Field(default=None, max_length=2000)


class EvaluateInput(BaseModel):
    setup_valid: bool = True
    applicable: bool = True
    target_checks: list[CheckInput]
    regression_checks: list[CheckInput]



class CandidateCreate(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=36)
    hypothesis: str = Field(min_length=1, max_length=2000)
    proposed_change: str = Field(min_length=1, max_length=10000)

    @field_validator("hypothesis", "proposed_change")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        return value.strip()


class CandidateEvaluationInput(BaseModel):
    setup_valid: bool = True
    applicable: bool = True
    target_checks: list[CheckInput]
    regression_checks: list[CheckInput]


class CandidateReviewInput(BaseModel):
    decision: Literal["accept", "reject"]
    reviewer: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("reviewer")
    @classmethod
    def require_nonblank_reviewer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reviewer cannot be blank.")
        return value.strip()
