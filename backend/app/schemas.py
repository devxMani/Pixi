"""Validated request schemas for the development API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.scenarios import Scenario, ScenarioAssertion


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


class CandidateRunEvaluationInput(BaseModel):
    baseline_run_id: str = Field(min_length=1, max_length=36)
    candidate_target_run_id: str = Field(min_length=1, max_length=36)
    regression_run_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("regression_run_ids")
    @classmethod
    def require_unique_regression_runs(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Regression run IDs must be unique.")
        return values





class BackupProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=120)
    created_at: datetime


class BackupScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=36)
    project_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=120)
    definition: Scenario
    created_at: datetime


class BackupObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=36)
    transcript: str = Field(max_length=100_000)
    latency_ms: float | None = Field(default=None, ge=0)
    tools_called: list[str] = Field(default_factory=list, max_length=100)
    error: str | None = Field(default=None, max_length=10_000)
    evidence_mode: Literal["simulated", "live"]
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    created_at: datetime


class BackupCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=36)
    sequence: int = Field(ge=0)
    assertion_id: str = Field(min_length=1, max_length=120)
    passed: bool | None
    error: str | None = Field(default=None, max_length=10_000)


class BackupRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=36)
    project_id: str = Field(min_length=1, max_length=36)
    scenario_id: str = Field(min_length=1, max_length=36)
    adapter_name: str = Field(min_length=1, max_length=100)
    evidence_mode: Literal["simulated", "live"]
    variant: Literal["simulated", "baseline", "candidate"] | None = None
    candidate_id: str | None = Field(default=None, max_length=36)
    agent_version: str | None = Field(default=None, max_length=200)
    status: Literal["passed", "failed", "inconclusive"]
    scenario_snapshot: Scenario
    started_at: datetime
    finished_at: datetime
    observations: list[BackupObservation] = Field(min_length=1, max_length=20)
    checks: list[BackupCheck] = Field(min_length=1, max_length=500)


class BackupCandidateEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=36)
    candidate_id: str = Field(min_length=1, max_length=36)
    outcome: Literal["passed", "failed", "inconclusive", "invalid_setup", "not_applicable"]
    reason: str = Field(max_length=10_000)
    evidence_mode: Literal["simulated", "live"]
    target_passed: bool
    regression_count: int = Field(ge=0)
    failed_regressions: list[str] = Field(default_factory=list, max_length=5000)
    critical_regressions: list[str] = Field(default_factory=list, max_length=5000)
    checks_snapshot: dict[str, Any]
    review_decision: Literal["accept", "reject"] | None = None
    reviewer: str | None = Field(default=None, max_length=120)
    review_note: str | None = Field(default=None, max_length=2000)
    reviewed_at: datetime | None = None
    created_at: datetime


class BackupCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=36)
    project_id: str = Field(min_length=1, max_length=36)
    scenario_id: str = Field(min_length=1, max_length=36)
    hypothesis: str = Field(min_length=1, max_length=20_000)
    proposed_change: str = Field(min_length=1, max_length=50_000)
    status: str = Field(min_length=1, max_length=40)
    production_applied: bool
    created_at: datetime
    evaluations: list[BackupCandidateEvaluation] = Field(default_factory=list, max_length=1000)


class ProjectImportInput(BaseModel):
    """Validated Pixi JSON export; import always creates a new project copy."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    exported_at: datetime
    project: BackupProject
    scenarios: list[BackupScenario] = Field(max_length=500)
    runs: list[BackupRun] = Field(max_length=5000)
    candidates: list[BackupCandidate] = Field(max_length=1000)
    name_override: str | None = Field(default=None, max_length=120)

    @field_validator("name_override")
    @classmethod
    def require_nonblank_override(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Restored project name cannot be blank.")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_snapshot_graph(self) -> ProjectImportInput:
        source_project_id = self.project.id
        scenario_ids = [item.id for item in self.scenarios]
        run_ids = [item.id for item in self.runs]
        candidate_ids = [item.id for item in self.candidates]

        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("Backup contains duplicate scenario IDs.")
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("Backup contains duplicate run IDs.")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Backup contains duplicate candidate IDs.")

        scenario_id_set = set(scenario_ids)
        run_id_set = set(run_ids)
        candidate_id_set = set(candidate_ids)

        for item in self.scenarios:
            if item.project_id != source_project_id:
                raise ValueError("Every scenario must belong to the exported project.")
            if item.definition.id != item.id or item.definition.name != item.name:
                raise ValueError("Scenario definition ID/name does not match its backup record.")

        for item in self.runs:
            if item.project_id != source_project_id:
                raise ValueError("Every run must belong to the exported project.")
            if item.scenario_id not in scenario_id_set:
                raise ValueError("A run references a scenario absent from the backup.")
            if item.scenario_snapshot.id != item.scenario_id:
                raise ValueError("Run scenario snapshot does not match its scenario ID.")
            if item.candidate_id is not None and item.candidate_id not in candidate_id_set:
                raise ValueError("A run references a candidate absent from the backup.")

        run_by_id = {item.id: item for item in self.runs}
        for candidate in self.candidates:
            if candidate.project_id != source_project_id:
                raise ValueError("Every candidate must belong to the exported project.")
            if candidate.scenario_id not in scenario_id_set:
                raise ValueError("A candidate references a scenario absent from the backup.")
            for evaluation in candidate.evaluations:
                if evaluation.candidate_id != candidate.id:
                    raise ValueError("Candidate evaluation references a different candidate.")
                snapshot = evaluation.checks_snapshot
                if snapshot.get("source") != "persisted_run_evidence":
                    continue

                baseline = snapshot.get("baseline")
                target = snapshot.get("candidate_target")
                if not isinstance(baseline, dict) or not isinstance(target, dict):
                    raise ValueError("An evidence evaluation must include baseline and candidate target details.")  # noqa: TRY004 - Pydantic requires ValueError for a validation response
                baseline_id = baseline.get("run_id")
                target_id = target.get("run_id")
                if (
                    not isinstance(baseline_id, str)
                    or not isinstance(target_id, str)
                    or baseline_id not in run_id_set
                    or target_id not in run_id_set
                ):
                    raise ValueError("An evaluation snapshot references a run absent from the backup.")
                baseline_run = run_by_id[baseline_id]
                target_run = run_by_id[target_id]
                if (
                    baseline_run.evidence_mode != "live"
                    or baseline_run.variant not in (None, "baseline")
                    or baseline_run.candidate_id is not None
                    or baseline_run.scenario_id != candidate.scenario_id
                    or target_run.evidence_mode != "live"
                    or target_run.variant != "candidate"
                    or target_run.candidate_id != candidate.id
                    or target_run.scenario_id != candidate.scenario_id
                ):
                    raise ValueError("Evaluation baseline/target provenance does not match the candidate.")
                target_snapshot_candidate_id = target.get("candidate_id")
                if target_snapshot_candidate_id != candidate.id:
                    raise ValueError("Evaluation target snapshot references a different candidate.")
                regressions = snapshot.get("regressions")
                if not isinstance(regressions, list) or not regressions:
                    raise ValueError("An evidence evaluation must include at least one regression run.")  # noqa: TRY004 - Pydantic requires ValueError for a validation response
                for regression in regressions:
                    if not isinstance(regression, dict):
                        raise ValueError("Regression evidence entries must be objects.")  # noqa: TRY004 - Pydantic requires ValueError for a validation response
                    regression_id = regression.get("run_id")
                    if not isinstance(regression_id, str) or regression_id not in run_id_set:
                        raise ValueError("A regression snapshot references a run absent from the backup.")
                    regression_run = run_by_id[regression_id]
                    if (
                        regression_run.evidence_mode != "live"
                        or regression_run.variant != "candidate"
                        or regression_run.candidate_id != candidate.id
                        or regression.get("scenario_id") != regression_run.scenario_id
                    ):
                        raise ValueError("Regression snapshot provenance does not match the candidate run.")
        return self


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
