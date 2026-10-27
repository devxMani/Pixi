"""Pixi FastAPI application entrypoint."""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters.fake import FixtureAgentAdapter
from app.adapters.http_json import build_configured_http_adapter
from app.db import get_db
from app.domain.evaluation import CheckResult, decide_evaluation
from app.domain.scenario_runner import run_scenario
from app.domain.scenarios import Scenario, ScenarioResult
from app.models import (
    CandidateEvaluationRecord,
    CandidateRecord,
    CheckRecord,
    ObservationRecord,
    ProjectRecord,
    RunRecord,
    ScenarioRecord,
)
from app.schemas import (
    CandidateCreate,
    CandidateEvaluationInput,
    CandidateReviewInput,
    CandidateRunEvaluationInput,
    EvaluateInput,
    FixtureObservationInput,
    ProjectCreate,
    ProjectImportInput,
    ScenarioCreate,
)

app = FastAPI(
    title="Pixi API",
    version="0.3.0",
    description="Development API for voice-agent scenario evaluation and evidence history.",
)
ROOT_DIR = Path(__file__).resolve().parents[2]


def require_development() -> None:
    """Fail closed until authentication and project authorization are implemented."""
    if os.getenv("APP_ENV", "production").lower() != "development":
        raise HTTPException(
            status_code=503,
            detail="API routes are development-only until authentication and authorization exist.",
        )


router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_development)])


def _project_or_404(db: Session, project_id: str) -> ProjectRecord:
    project = db.get(ProjectRecord, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _serialize_candidate(db: Session, candidate: CandidateRecord) -> dict[str, object]:
    latest = db.scalars(
        select(CandidateEvaluationRecord)
        .where(CandidateEvaluationRecord.candidate_id == candidate.id)
        .order_by(CandidateEvaluationRecord.created_at.desc())
        .limit(1)
    ).first()
    evaluation = None
    if latest is not None:
        evaluation = {
            "id": latest.id,
            "outcome": latest.outcome,
            "reason": latest.reason,
            "evidence_mode": latest.evidence_mode,
            "target_passed": latest.target_passed,
            "regression_count": latest.regression_count,
            "failed_regressions": latest.failed_regressions,
            "critical_regressions": latest.critical_regressions,
            "checks_snapshot": latest.checks_snapshot,
            "review_decision": latest.review_decision,
            "reviewer": latest.reviewer,
            "review_note": latest.review_note,
            "reviewed_at": latest.reviewed_at,
            "created_at": latest.created_at,
        }
    return {
        "id": candidate.id,
        "project_id": candidate.project_id,
        "scenario_id": candidate.scenario_id,
        "hypothesis": candidate.hypothesis,
        "proposed_change": candidate.proposed_change,
        "status": candidate.status,
        "production_applied": candidate.production_applied,
        "created_at": candidate.created_at,
        "latest_evaluation": evaluation,
    }


def _serialize_run(db: Session, run: RunRecord) -> dict[str, object]:
    observations = db.scalars(
        select(ObservationRecord)
        .where(ObservationRecord.run_id == run.id)
        .order_by(ObservationRecord.created_at)
    ).all()
    checks = db.scalars(
        select(CheckRecord)
        .where(CheckRecord.run_id == run.id)
        .order_by(CheckRecord.sequence)
    ).all()
    return {
        "id": run.id,
        "project_id": run.project_id,
        "scenario_id": run.scenario_id,
        "adapter_name": run.adapter_name,
        "evidence_mode": run.evidence_mode,
        "variant": run.variant,
        "candidate_id": run.candidate_id,
        "agent_version": run.agent_version,
        "status": run.status,
        "scenario_snapshot": run.scenario_snapshot,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "observations": [
            {
                "id": item.id,
                "transcript": item.transcript,
                "latency_ms": item.latency_ms,
                "tools_called": item.tools_called,
                "error": item.error,
                "evidence_mode": item.evidence_mode,
                "provider": item.provider,
                "model": item.model,
                "created_at": item.created_at,
            }
            for item in observations
        ],
        "checks": [
            {
                "id": item.id,
                "sequence": item.sequence,
                "assertion_id": item.assertion_id,
                "passed": item.passed,
                "error": item.error,
            }
            for item in checks
        ],
    }


def _persist_scenario_result(
    db: Session,
    *,
    project_id: str,
    scenario_id: str,
    scenario: Scenario,
    result: ScenarioResult,
    started_at: datetime,
    finished_at: datetime,
    idempotency_key: str | None = None,
    fingerprint: str | None = None,
) -> tuple[RunRecord, bool]:
    """Persist evidence transactionally; return (run, is_idempotency_replay)."""
    run = RunRecord(
        id=str(uuid4()),
        project_id=project_id,
        scenario_id=scenario_id,
        adapter_name=result.adapter_name,
        evidence_mode=result.evidence_mode.value,
        status=result.status.value,
        scenario_snapshot=scenario.model_dump(mode="json"),
        idempotency_key=idempotency_key,
        idempotency_fingerprint=fingerprint,
        candidate_id=result.observation.candidate_id,
        variant=result.observation.variant.value,
        agent_version=result.observation.agent_version,
        started_at=started_at,
        finished_at=finished_at,
    )
    try:
        db.add(run)
        db.flush()
        db.add(
            ObservationRecord(
                id=str(uuid4()),
                run_id=run.id,
                transcript=result.observation.transcript,
                latency_ms=result.observation.latency_ms,
                tools_called=result.observation.tools_called,
                error=result.observation.error,
                evidence_mode=result.observation.evidence_mode.value,
                provider=result.observation.provider,
                model=result.observation.model,
            )
        )
        for sequence, check in enumerate(result.checks):
            db.add(
                CheckRecord(
                    id=str(uuid4()),
                    run_id=run.id,
                    sequence=sequence,
                    assertion_id=check.name,
                    passed=check.passed,
                    error=check.error,
                )
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key is not None:
            existing = db.scalars(
                select(RunRecord).where(
                    RunRecord.project_id == project_id,
                    RunRecord.scenario_id == scenario_id,
                    RunRecord.idempotency_key == idempotency_key,
                )
            ).first()
            if existing is not None and existing.idempotency_fingerprint == fingerprint:
                return existing, True
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This Idempotency-Key was concurrently used with a different request payload.",
                ) from exc
        raise
    db.refresh(run)
    return run, False


@app.get("/", include_in_schema=False)
def prototype_page() -> FileResponse:
    """Serve the preserved Miso prototype from the same origin as the local API."""
    return FileResponse(ROOT_DIR / "index.html")


@app.get("/console.html", include_in_schema=False)
def console_page() -> FileResponse:
    """Serve the API-backed project and evidence workspace."""
    return FileResponse(ROOT_DIR / "console.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pixi-api"}


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectCreate, db: Annotated[Session, Depends(get_db)]
) -> dict[str, object]:
    project = ProjectRecord(id=str(uuid4()), name=payload.name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "created_at": project.created_at}


@router.get("/projects")
def list_projects(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    projects = db.scalars(
        select(ProjectRecord).order_by(ProjectRecord.created_at.desc()).limit(limit)
    ).all()
    return [
        {"id": project.id, "name": project.name, "created_at": project.created_at}
        for project in projects
    ]


@router.post("/projects/{project_id}/scenarios", status_code=201)
def create_scenario(
    project_id: str,
    payload: ScenarioCreate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    _project_or_404(db, project_id)
    scenario_id = str(uuid4())
    scenario = Scenario(
        id=scenario_id,
        name=payload.name,
        turns=payload.turns,
        assertions=payload.assertions,
    )
    record = ScenarioRecord(
        id=scenario_id,
        project_id=project_id,
        name=payload.name,
        definition=scenario.model_dump(mode="json"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "project_id": record.project_id,
        "name": record.name,
        "definition": record.definition,
        "created_at": record.created_at,
    }


@router.get("/projects/{project_id}/scenarios")
def list_scenarios(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    _project_or_404(db, project_id)
    scenarios = db.scalars(
        select(ScenarioRecord)
        .where(ScenarioRecord.project_id == project_id)
        .order_by(ScenarioRecord.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": item.id,
            "project_id": item.project_id,
            "name": item.name,
            "definition": item.definition,
            "created_at": item.created_at,
        }
        for item in scenarios
    ]


@router.get("/projects/{project_id}/runs")
def list_project_runs(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, object]]:
    _project_or_404(db, project_id)
    runs = db.scalars(
        select(RunRecord)
        .where(RunRecord.project_id == project_id)
        .order_by(RunRecord.started_at.desc())
        .limit(limit)
    ).all()
    return [_serialize_run(db, run) for run in runs]


@router.post("/projects/{project_id}/scenarios/{scenario_id}/demo-runs", status_code=201)
async def create_demo_run(
    project_id: str,
    scenario_id: str,
    fixture: FixtureObservationInput,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> dict[str, object]:
    """Run a fixture only; retries with one idempotency key create at most one saved run."""
    _project_or_404(db, project_id)
    scenario_record = db.get(ScenarioRecord, scenario_id)
    if scenario_record is None or scenario_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scenario not found in this project.")

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            raise HTTPException(status_code=422, detail="Idempotency-Key cannot be blank.")
        canonical_payload = json.dumps(
            {
                "scenario_id": scenario_id,
                "fixture": fixture.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        existing = db.scalars(
            select(RunRecord).where(
                RunRecord.project_id == project_id,
                RunRecord.scenario_id == scenario_id,
                RunRecord.idempotency_key == idempotency_key,
            )
        ).first()
        if existing is not None:
            if existing.idempotency_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="This Idempotency-Key was already used with a different request payload.",
                )
            response.status_code = 200
            return _serialize_run(db, existing)
    else:
        fingerprint = None

    scenario = Scenario.model_validate(scenario_record.definition)
    adapter = FixtureAgentAdapter(
        transcript=fixture.transcript,
        latency_ms=fixture.latency_ms,
        tools_called=fixture.tools_called,
        error=fixture.error,
    )
    started_at = datetime.now(UTC)
    result = await run_scenario(adapter, scenario)
    finished_at = datetime.now(UTC)

    run, replayed = _persist_scenario_result(
        db,
        project_id=project_id,
        scenario_id=scenario_id,
        scenario=scenario,
        result=result,
        started_at=started_at,
        finished_at=finished_at,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if replayed:
        response.status_code = 200
    return _serialize_run(db, run)


@router.post(
    "/projects/{project_id}/scenarios/{scenario_id}/agent-runs",
    status_code=201,
)
async def create_agent_run(
    project_id: str,
    scenario_id: str,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
    candidate_id: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> dict[str, object]:
    """Execute one scenario against the configured external agent bridge."""
    _project_or_404(db, project_id)
    scenario_record = db.get(ScenarioRecord, scenario_id)
    if scenario_record is None or scenario_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scenario not found in this project.")
    candidate_record: CandidateRecord | None = None
    candidate_context: dict[str, str] | None = None
    if candidate_id is not None:
        candidate_record = db.get(CandidateRecord, candidate_id)
        if candidate_record is None or candidate_record.project_id != project_id:
            raise HTTPException(status_code=404, detail="Candidate not found in this project.")
        candidate_context = {
            "id": candidate_record.id,
            "hypothesis": candidate_record.hypothesis,
            "proposed_change": candidate_record.proposed_change,
        }
    try:
        adapter = build_configured_http_adapter(candidate=candidate_context)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Live agent bridge is not configured or its server-side configuration is invalid.",
        ) from exc

    scenario = Scenario.model_validate(scenario_record.definition)
    fingerprint = None
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            raise HTTPException(status_code=422, detail="Idempotency-Key cannot be blank.")
        canonical_payload = json.dumps(
            {
                "scenario_id": scenario_id,
                "scenario": scenario.model_dump(mode="json"),
                "endpoint": adapter.endpoint,
                "candidate_id": candidate_id,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        existing = db.scalars(
            select(RunRecord).where(
                RunRecord.project_id == project_id,
                RunRecord.scenario_id == scenario_id,
                RunRecord.idempotency_key == idempotency_key,
            )
        ).first()
        if existing is not None:
            if existing.idempotency_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="This Idempotency-Key was already used with a different request payload.",
                )
            response.status_code = 200
            return _serialize_run(db, existing)

    started_at = datetime.now(UTC)
    result = await run_scenario(adapter, scenario)
    finished_at = datetime.now(UTC)
    run, replayed = _persist_scenario_result(
        db,
        project_id=project_id,
        scenario_id=scenario_id,
        scenario=scenario,
        result=result,
        started_at=started_at,
        finished_at=finished_at,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if replayed:
        response.status_code = 200
    return _serialize_run(db, run)


@router.get("/runs/{run_id}")
def get_run(
    run_id: str, db: Annotated[Session, Depends(get_db)]
) -> dict[str, object]:
    run = db.get(RunRecord, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _serialize_run(db, run)


@router.post("/projects/{project_id}/candidates", status_code=201)
def create_candidate(
    project_id: str,
    payload: CandidateCreate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    _project_or_404(db, project_id)
    scenario = db.get(ScenarioRecord, payload.scenario_id)
    if scenario is None or scenario.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scenario not found in this project.")
    candidate = CandidateRecord(
        id=str(uuid4()),
        project_id=project_id,
        scenario_id=payload.scenario_id,
        hypothesis=payload.hypothesis,
        proposed_change=payload.proposed_change,
        status="proposed",
        production_applied=False,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(db, candidate)


@router.get("/projects/{project_id}/candidates")
def list_candidates(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, object]]:
    _project_or_404(db, project_id)
    candidates = db.scalars(
        select(CandidateRecord)
        .where(CandidateRecord.project_id == project_id)
        .order_by(CandidateRecord.created_at.desc())
        .limit(limit)
    ).all()
    return [_serialize_candidate(db, candidate) for candidate in candidates]


@router.post("/candidates/{candidate_id}/evaluate", status_code=201)
def evaluate_candidate(
    candidate_id: str,
    payload: CandidateEvaluationInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    candidate = db.get(CandidateRecord, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    targets = tuple(CheckResult(**item.model_dump()) for item in payload.target_checks)
    regressions = tuple(CheckResult(**item.model_dump()) for item in payload.regression_checks)
    decision = decide_evaluation(
        setup_valid=payload.setup_valid,
        applicable=payload.applicable,
        target_checks=targets,
        regression_checks=regressions,
    )
    checks = {
        "target": [
            {"name": item.name, "passed": item.passed, "critical": item.critical, "error": item.error}
            for item in targets
        ],
        "regressions": [
            {"name": item.name, "passed": item.passed, "critical": item.critical, "error": item.error}
            for item in regressions
        ],
        "setup_valid": payload.setup_valid,
        "applicable": payload.applicable,
    }
    db.add(
        CandidateEvaluationRecord(
            id=str(uuid4()),
            candidate_id=candidate.id,
            outcome=decision.outcome.value,
            reason=decision.reason,
            evidence_mode="simulated",
            target_passed=decision.target_passed,
            regression_count=decision.regression_count,
            failed_regressions=list(decision.failed_regressions),
            critical_regressions=list(decision.critical_regressions),
            checks_snapshot=checks,
        )
    )
    if decision.outcome.value == "passed":
        candidate.status = "validated_for_review"
    elif decision.outcome.value == "failed":
        candidate.status = "gate_failed"
    else:
        candidate.status = decision.outcome.value
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(db, candidate)


def _checks_from_saved_run(
    db: Session, run: RunRecord, *, include_scenario_name: bool = False
) -> list[CheckResult]:
    """Rebuild immutable check results from a persisted run and its scenario snapshot."""
    assertions = run.scenario_snapshot.get("assertions", [])
    assertion_meta = {
        item.get("id"): item for item in assertions if isinstance(item, dict)
    }
    scenario_name = str(run.scenario_snapshot.get("name") or run.scenario_id)
    saved_checks = db.scalars(
        select(CheckRecord)
        .where(CheckRecord.run_id == run.id)
        .order_by(CheckRecord.sequence)
    ).all()
    output: list[CheckResult] = []
    for check in saved_checks:
        assertion = assertion_meta.get(check.assertion_id, {})
        name = (
            f"{scenario_name}::{check.assertion_id}"
            if include_scenario_name
            else check.assertion_id
        )
        output.append(
            CheckResult(
                name=name,
                passed=check.passed,
                critical=bool(assertion.get("critical", False)),
                error=check.error,
            )
        )
    return output


@router.post("/candidates/{candidate_id}/evaluate-runs", status_code=201)
def evaluate_candidate_from_runs(
    candidate_id: str,
    payload: CandidateRunEvaluationInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Gate a candidate using persisted baseline, candidate-target, and regression run evidence."""
    candidate = db.get(CandidateRecord, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    regression_ids = payload.regression_run_ids
    if payload.baseline_run_id == payload.candidate_target_run_id:
        raise HTTPException(status_code=422, detail="Baseline and candidate target runs must differ.")
    if payload.baseline_run_id in regression_ids or payload.candidate_target_run_id in regression_ids:
        raise HTTPException(status_code=422, detail="Run IDs must be unique across evaluation roles.")

    baseline_run = db.get(RunRecord, payload.baseline_run_id)
    target_run = db.get(RunRecord, payload.candidate_target_run_id)
    regression_runs = [db.get(RunRecord, run_id) for run_id in regression_ids]
    if baseline_run is None or target_run is None or any(run is None for run in regression_runs):
        raise HTTPException(status_code=404, detail="One or more referenced runs were not found.")

    all_runs = [baseline_run, target_run, *regression_runs]
    if any(run.project_id != candidate.project_id for run in all_runs):
        raise HTTPException(status_code=404, detail="One or more runs are outside this project.")
    if baseline_run.scenario_id != candidate.scenario_id or target_run.scenario_id != candidate.scenario_id:
        raise HTTPException(
            status_code=409,
            detail="Baseline and candidate target runs must use the candidate's target scenario.",
        )
    if baseline_run.evidence_mode != "live" or baseline_run.variant != "baseline" or baseline_run.candidate_id:
        raise HTTPException(
            status_code=409,
            detail="The baseline run must be a recorded live baseline variant.",
        )
    if target_run.evidence_mode != "live" or target_run.variant != "candidate" or target_run.candidate_id != candidate.id:
        raise HTTPException(
            status_code=409,
            detail="The candidate target run must be live evidence for this candidate variant.",
        )
    if any(
        run.evidence_mode != "live"
        or run.variant != "candidate"
        or run.candidate_id != candidate.id
        for run in regression_runs
    ):
        raise HTTPException(
            status_code=409,
            detail="Every regression run must be live evidence for this same candidate variant.",
        )
    regression_scenarios = [run.scenario_id for run in regression_runs]
    if candidate.scenario_id in regression_scenarios:
        raise HTTPException(
            status_code=422,
            detail="Regression runs must cover scenarios other than the target scenario.",
        )
    if len(regression_scenarios) != len(set(regression_scenarios)):
        raise HTTPException(
            status_code=422,
            detail="Use one regression run per distinct scenario.",
        )

    expected_regression_scenarios = set(
        db.scalars(
            select(ScenarioRecord.id).where(
                ScenarioRecord.project_id == candidate.project_id,
                ScenarioRecord.id != candidate.scenario_id,
            )
        ).all()
    )
    submitted_regression_scenarios = set(regression_scenarios)
    if not expected_regression_scenarios:
        raise HTTPException(
            status_code=409,
            detail="Create at least one non-target scenario before evaluating a candidate.",
        )
    missing_regressions = expected_regression_scenarios - submitted_regression_scenarios
    unexpected_regressions = submitted_regression_scenarios - expected_regression_scenarios
    if missing_regressions:
        raise HTTPException(
            status_code=409,
            detail=(
                "Regression suite is incomplete. Run the candidate against every non-target "
                f"scenario in this project; missing {len(missing_regressions)} scenario(s)."
            ),
        )
    if unexpected_regressions:
        raise HTTPException(
            status_code=422,
            detail="Regression runs must belong to non-target scenarios in this project.",
        )

    baseline_version = baseline_run.agent_version
    candidate_versions = [target_run.agent_version, *(run.agent_version for run in regression_runs)]
    has_missing_versions = not baseline_version or any(not version for version in candidate_versions)
    versions_disagree = (
        not has_missing_versions
        and (len(set(candidate_versions)) != 1 or baseline_version == candidate_versions[0])
    )

    target_checks = _checks_from_saved_run(db, target_run)
    regression_checks = [
        check
        for run in regression_runs
        for check in _checks_from_saved_run(db, run, include_scenario_name=True)
    ]
    applicable = baseline_run.status != "passed"
    setup_valid = not versions_disagree
    if baseline_run.status == "inconclusive":
        target_checks = [
            CheckResult(
                name="baseline-run",
                passed=None,
                error="Baseline run was inconclusive; target failure precondition is unknown.",
            ),
            *target_checks,
        ]
    if has_missing_versions:
        target_checks = [
            *target_checks,
            CheckResult(
                name="agent-version",
                passed=None,
                error="A required run did not return an immutable agent version.",
            ),
        ]
    decision = decide_evaluation(
        setup_valid=setup_valid,
        applicable=applicable,
        target_checks=target_checks,
        regression_checks=regression_checks,
    )
    checks_snapshot = {
        "source": "persisted_run_evidence",
        "baseline": {
            "run_id": baseline_run.id,
            "status": baseline_run.status,
            "agent_version": baseline_run.agent_version,
            "checks": [
                {"name": check.name, "passed": check.passed, "critical": check.critical, "error": check.error}
                for check in _checks_from_saved_run(db, baseline_run)
            ],
        },
        "candidate_target": {
            "run_id": target_run.id,
            "candidate_id": target_run.candidate_id,
            "agent_version": target_run.agent_version,
            "checks": [
                {"name": check.name, "passed": check.passed, "critical": check.critical, "error": check.error}
                for check in target_checks
            ],
        },
        "regressions": [
            {
                "run_id": run.id,
                "scenario_id": run.scenario_id,
                "agent_version": run.agent_version,
                "checks": [
                    {"name": check.name, "passed": check.passed, "critical": check.critical, "error": check.error}
                    for check in _checks_from_saved_run(db, run, include_scenario_name=True)
                ],
            }
            for run in regression_runs
        ],
        "setup_valid": setup_valid,
        "applicable": applicable,
    }
    db.add(
        CandidateEvaluationRecord(
            id=str(uuid4()),
            candidate_id=candidate.id,
            outcome=decision.outcome.value,
            reason=decision.reason,
            evidence_mode="live",
            target_passed=decision.target_passed,
            regression_count=decision.regression_count,
            failed_regressions=list(decision.failed_regressions),
            critical_regressions=list(decision.critical_regressions),
            checks_snapshot=checks_snapshot,
        )
    )
    if decision.outcome.value == "passed":
        candidate.status = "validated_for_review"
    elif decision.outcome.value == "failed":
        candidate.status = "gate_failed"
    else:
        candidate.status = decision.outcome.value
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(db, candidate)


@router.post("/candidates/{candidate_id}/review")
def review_candidate(
    candidate_id: str,
    payload: CandidateReviewInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    candidate = db.get(CandidateRecord, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    latest = db.scalars(
        select(CandidateEvaluationRecord)
        .where(CandidateEvaluationRecord.candidate_id == candidate.id)
        .order_by(CandidateEvaluationRecord.created_at.desc())
        .limit(1)
    ).first()
    if latest is None:
        raise HTTPException(status_code=409, detail="Evaluate the candidate before review.")
    if payload.decision == "accept":
        if latest.outcome != "passed":
            raise HTTPException(status_code=409, detail="Candidate must pass evaluation before approval.")
        if latest.evidence_mode != "live":
            raise HTTPException(
                status_code=409,
                detail="Simulated evidence cannot be approved for release. A passing live-agent evaluation is required.",
            )
        candidate.status = "accepted"
    else:
        candidate.status = "rejected"
    latest.review_decision = payload.decision
    latest.reviewer = payload.reviewer
    latest.review_note = payload.note
    latest.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(db, candidate)


@router.post("/evaluations/decide")
def evaluation_decision(payload: EvaluateInput) -> dict[str, object]:
    """Evaluate supplied checks; this endpoint does not call an agent."""
    decision = decide_evaluation(
        setup_valid=payload.setup_valid,
        applicable=payload.applicable,
        target_checks=(CheckResult(**check.model_dump()) for check in payload.target_checks),
        regression_checks=(CheckResult(**check.model_dump()) for check in payload.regression_checks),
    )
    return {
        "outcome": decision.outcome.value,
        "reason": decision.reason,
        "target_passed": decision.target_passed,
        "regression_count": decision.regression_count,
        "failed_regressions": list(decision.failed_regressions),
        "critical_regressions": list(decision.critical_regressions),
    }


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    """Export a complete, versioned project snapshot for a user-initiated backup."""
    project = _project_or_404(db, project_id)
    scenarios = db.scalars(
        select(ScenarioRecord)
        .where(ScenarioRecord.project_id == project_id)
        .order_by(ScenarioRecord.created_at)
    ).all()
    runs = db.scalars(
        select(RunRecord)
        .where(RunRecord.project_id == project_id)
        .order_by(RunRecord.started_at)
    ).all()
    candidates = db.scalars(
        select(CandidateRecord)
        .where(CandidateRecord.project_id == project_id)
        .order_by(CandidateRecord.created_at)
    ).all()

    candidate_snapshots: list[dict[str, object]] = []
    for candidate in candidates:
        evaluations = db.scalars(
            select(CandidateEvaluationRecord)
            .where(CandidateEvaluationRecord.candidate_id == candidate.id)
            .order_by(CandidateEvaluationRecord.created_at)
        ).all()
        candidate_snapshots.append(
            {
                "id": candidate.id,
                "project_id": candidate.project_id,
                "scenario_id": candidate.scenario_id,
                "hypothesis": candidate.hypothesis,
                "proposed_change": candidate.proposed_change,
                "status": candidate.status,
                "production_applied": candidate.production_applied,
                "created_at": candidate.created_at,
                "evaluations": [
                    {
                        "id": evaluation.id,
                        "candidate_id": evaluation.candidate_id,
                        "outcome": evaluation.outcome,
                        "reason": evaluation.reason,
                        "evidence_mode": evaluation.evidence_mode,
                        "target_passed": evaluation.target_passed,
                        "regression_count": evaluation.regression_count,
                        "failed_regressions": evaluation.failed_regressions,
                        "critical_regressions": evaluation.critical_regressions,
                        "checks_snapshot": evaluation.checks_snapshot,
                        "review_decision": evaluation.review_decision,
                        "reviewer": evaluation.reviewer,
                        "review_note": evaluation.review_note,
                        "reviewed_at": evaluation.reviewed_at,
                        "created_at": evaluation.created_at,
                    }
                    for evaluation in evaluations
                ],
            }
        )

    snapshot = {
        "schema_version": 1,
        "exported_at": datetime.now(UTC),
        "project": {
            "id": project.id,
            "name": project.name,
            "created_at": project.created_at,
        },
        "scenarios": [
            {
                "id": scenario.id,
                "project_id": scenario.project_id,
                "name": scenario.name,
                "definition": scenario.definition,
                "created_at": scenario.created_at,
            }
            for scenario in scenarios
        ],
        "runs": [_serialize_run(db, run) for run in runs],
        "candidates": candidate_snapshots,
    }
    return JSONResponse(
        content=jsonable_encoder(snapshot),
        headers={
            "Content-Disposition": f'attachment; filename="pixi-project-{project_id}.json"'
        },
    )


def _remap_evaluation_snapshot(
    source_snapshot: dict[str, object],
    *,
    run_id_map: dict[str, str],
    scenario_id_map: dict[str, str],
    candidate_id_map: dict[str, str],
) -> dict[str, object]:
    """Copy a saved evaluation snapshot and remap its internal evidence references."""
    snapshot = deepcopy(source_snapshot)
    if snapshot.get("source") != "persisted_run_evidence":
        return snapshot

    for section in ("baseline", "candidate_target"):
        data = snapshot.get(section)
        if not isinstance(data, dict):
            continue
        run_id = data.get("run_id")
        if isinstance(run_id, str):
            data["run_id"] = run_id_map[run_id]
        if section == "candidate_target":
            candidate_id = data.get("candidate_id")
            if isinstance(candidate_id, str):
                data["candidate_id"] = candidate_id_map[candidate_id]

    regressions = snapshot.get("regressions", [])
    if isinstance(regressions, list):
        for regression in regressions:
            if not isinstance(regression, dict):
                continue
            run_id = regression.get("run_id")
            scenario_id = regression.get("scenario_id")
            if isinstance(run_id, str):
                regression["run_id"] = run_id_map[run_id]
            if isinstance(scenario_id, str):
                regression["scenario_id"] = scenario_id_map[scenario_id]
    return snapshot


@router.post("/projects/import", status_code=201)
def import_project_backup(
    payload: ProjectImportInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Restore a validated JSON backup as a new project without overwriting existing data."""
    source_project_id = payload.project.id
    restored_name = payload.name_override or f"{payload.project.name[:109]} (restored)"
    restored_name = restored_name[:120]
    project_id = str(uuid4())
    scenario_id_map = {item.id: str(uuid4()) for item in payload.scenarios}
    run_id_map = {item.id: str(uuid4()) for item in payload.runs}
    candidate_id_map = {item.id: str(uuid4()) for item in payload.candidates}

    project = ProjectRecord(id=project_id, name=restored_name)
    try:
        db.add(project)
        db.flush()

        scenario_records = []
        for item in payload.scenarios:
            definition = item.definition.model_dump(mode="json")
            definition["id"] = scenario_id_map[item.id]
            scenario_records.append(
                ScenarioRecord(
                    id=scenario_id_map[item.id],
                    project_id=project_id,
                    name=item.name,
                    definition=definition,
                    created_at=item.created_at,
                )
            )
        db.add_all(scenario_records)
        db.flush()

        candidate_records = [
            CandidateRecord(
                id=candidate_id_map[item.id],
                project_id=project_id,
                scenario_id=scenario_id_map[item.scenario_id],
                hypothesis=item.hypothesis,
                proposed_change=item.proposed_change,
                status=item.status,
                production_applied=item.production_applied,
                created_at=item.created_at,
            )
            for item in payload.candidates
        ]
        db.add_all(candidate_records)
        db.flush()

        run_records = []
        for item in payload.runs:
            scenario_snapshot = item.scenario_snapshot.model_dump(mode="json")
            scenario_snapshot["id"] = scenario_id_map[item.scenario_id]
            if item.variant is not None:
                variant = item.variant
            else:
                # Older schema-v1 exports predate explicit variants and versions. Preserve
                # live provenance, but lack of agent_version will keep these runs ineligible
                # for the new versioned candidate gate.
                variant = "baseline" if item.evidence_mode == "live" else "simulated"
            run_records.append(
                RunRecord(
                    id=run_id_map[item.id],
                    project_id=project_id,
                    scenario_id=scenario_id_map[item.scenario_id],
                    adapter_name=item.adapter_name,
                    evidence_mode=item.evidence_mode,
                    status=item.status,
                    scenario_snapshot=scenario_snapshot,
                    idempotency_key=None,
                    idempotency_fingerprint=None,
                    candidate_id=(
                        candidate_id_map[item.candidate_id] if item.candidate_id is not None else None
                    ),
                    variant=variant,
                    agent_version=item.agent_version,
                    started_at=item.started_at,
                    finished_at=item.finished_at,
                )
            )
        db.add_all(run_records)
        db.flush()

        for item in payload.runs:
            new_run_id = run_id_map[item.id]
            db.add_all(
                [
                    ObservationRecord(
                        id=str(uuid4()),
                        run_id=new_run_id,
                        transcript=observation.transcript,
                        latency_ms=observation.latency_ms,
                        tools_called=observation.tools_called,
                        error=observation.error,
                        evidence_mode=observation.evidence_mode,
                        provider=observation.provider,
                        model=observation.model,
                        created_at=observation.created_at,
                    )
                    for observation in item.observations
                ]
            )
            db.add_all(
                [
                    CheckRecord(
                        id=str(uuid4()),
                        run_id=new_run_id,
                        sequence=check.sequence,
                        assertion_id=check.assertion_id,
                        passed=check.passed,
                        error=check.error,
                    )
                    for check in item.checks
                ]
            )

        for candidate in payload.candidates:
            new_candidate_id = candidate_id_map[candidate.id]
            db.add_all(
                [
                    CandidateEvaluationRecord(
                        id=str(uuid4()),
                        candidate_id=new_candidate_id,
                        outcome=evaluation.outcome,
                        reason=evaluation.reason,
                        evidence_mode=evaluation.evidence_mode,
                        target_passed=evaluation.target_passed,
                        regression_count=evaluation.regression_count,
                        failed_regressions=evaluation.failed_regressions,
                        critical_regressions=evaluation.critical_regressions,
                        checks_snapshot=_remap_evaluation_snapshot(
                            evaluation.checks_snapshot,
                            run_id_map=run_id_map,
                            scenario_id_map=scenario_id_map,
                            candidate_id_map=candidate_id_map,
                        ),
                        review_decision=evaluation.review_decision,
                        reviewer=evaluation.reviewer,
                        review_note=evaluation.review_note,
                        reviewed_at=evaluation.reviewed_at,
                        created_at=evaluation.created_at,
                    )
                    for evaluation in candidate.evaluations
                ]
            )

        db.commit()
        db.refresh(project)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="Backup passed validation but could not be restored into this database.",
        ) from exc

    return {
        "id": project.id,
        "name": project.name,
        "restored_from": source_project_id,
        "created_at": project.created_at,
        "counts": {
            "scenarios": len(payload.scenarios),
            "runs": len(payload.runs),
            "candidates": len(payload.candidates),
            "evaluations": sum(len(item.evaluations) for item in payload.candidates),
        },
    }


app.include_router(router)
