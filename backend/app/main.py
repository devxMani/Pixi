"""Pixi FastAPI application entrypoint."""
from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.fake import FixtureAgentAdapter
from app.db import get_db
from app.domain.evaluation import CheckResult, decide_evaluation
from app.domain.scenario_runner import run_scenario
from app.domain.scenarios import Scenario
from app.models import CheckRecord, ObservationRecord, ProjectRecord, RunRecord, ScenarioRecord
from app.schemas import EvaluateInput, FixtureObservationInput, ProjectCreate, ScenarioCreate


app = FastAPI(
    title="Pixi API",
    version="0.2.0",
    description="Development API for voice-agent scenario evaluation and evidence history.",
)


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


@router.post("/projects/{project_id}/scenarios/{scenario_id}/demo-runs", status_code=201)
async def create_demo_run(
    project_id: str,
    scenario_id: str,
    fixture: FixtureObservationInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Run a fixture only; this endpoint never talks to an external model or phone agent."""
    _project_or_404(db, project_id)
    scenario_record = db.get(ScenarioRecord, scenario_id)
    if scenario_record is None or scenario_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scenario not found in this project.")

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

    run = RunRecord(
        id=str(uuid4()),
        project_id=project_id,
        scenario_id=scenario_id,
        adapter_name=result.adapter_name,
        evidence_mode=result.evidence_mode.value,
        status=result.status.value,
        scenario_snapshot=scenario.model_dump(mode="json"),
        started_at=started_at,
        finished_at=finished_at,
    )
    db.add(run)
    db.flush()
    observation = ObservationRecord(
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
    db.add(observation)
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
    db.refresh(run)
    return _serialize_run(db, run)


@router.get("/runs/{run_id}")
def get_run(
    run_id: str, db: Annotated[Session, Depends(get_db)]
) -> dict[str, object]:
    run = db.get(RunRecord, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _serialize_run(db, run)


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


app.include_router(router)
