"""Pure evaluation decision policy; errors and missing evidence never pass."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class Outcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    INVALID_SETUP = "invalid_setup"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool | None
    critical: bool = False
    error: str | None = None


@dataclass(frozen=True)
class EvaluationDecision:
    outcome: Outcome
    reason: str
    target_passed: bool
    regression_count: int
    failed_regressions: tuple[str, ...]
    critical_regressions: tuple[str, ...]


def decide_evaluation(*, setup_valid: bool, applicable: bool,
                      target_checks: Iterable[CheckResult],
                      regression_checks: Iterable[CheckResult]) -> EvaluationDecision:
    """Return a conservative outcome for the target checks and required regressions."""
    if not applicable:
        return EvaluationDecision(Outcome.NOT_APPLICABLE, "Experiment does not apply to this configuration.", False, 0, (), ())
    if not setup_valid:
        return EvaluationDecision(Outcome.INVALID_SETUP, "Required preconditions were not met.", False, 0, (), ())

    target = tuple(target_checks)
    regressions = tuple(regression_checks)
    if not target:
        return EvaluationDecision(Outcome.INCONCLUSIVE, "No target checks were executed.", False, len(regressions), (), ())

    missing_or_errored = [c for c in (*target, *regressions) if c.error or c.passed is None]
    failed = tuple(c.name for c in regressions if c.passed is False)
    critical = tuple(c.name for c in regressions if c.passed is False and c.critical)
    target_passed = all(c.passed is True and c.error is None for c in target)
    if missing_or_errored:
        return EvaluationDecision(Outcome.INCONCLUSIVE, "At least one required check is missing or errored.", target_passed, len(regressions), failed, critical)
    if critical:
        return EvaluationDecision(Outcome.FAILED, "A critical regression failed.", target_passed, len(regressions), failed, critical)
    if failed:
        return EvaluationDecision(Outcome.FAILED, "One or more regression checks failed.", target_passed, len(regressions), failed, ())
    if not target_passed:
        return EvaluationDecision(Outcome.FAILED, "One or more target checks failed.", False, len(regressions), (), ())
    if not regressions:
        return EvaluationDecision(Outcome.INCONCLUSIVE, "The required regression suite was empty.", True, 0, (), ())
    return EvaluationDecision(Outcome.PASSED, "Target checks passed and the regression suite completed without failures.", True, len(regressions), (), ())
