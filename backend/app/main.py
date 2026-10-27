"""Pixi FastAPI application entrypoint."""
from fastapi import FastAPI
from pydantic import BaseModel

from app.domain.evaluation import CheckResult, decide_evaluation

app = FastAPI(title="Pixi API", version="0.1.0", description="Evaluation and reliability API for voice agents.")


class CheckInput(BaseModel):
    name: str
    passed: bool | None
    critical: bool = False
    error: str | None = None


class EvaluateInput(BaseModel):
    setup_valid: bool = True
    applicable: bool = True
    target_checks: list[CheckInput]
    regression_checks: list[CheckInput]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pixi-api"}


@app.post("/api/v1/evaluations/decide")
def evaluation_decision(payload: EvaluateInput) -> dict[str, object]:
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
