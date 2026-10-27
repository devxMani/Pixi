"""Pure evaluation decision policy; missing evidence is never a pass."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


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


def decide_evaluation(
    *,
    setup_valid: bool,
    applicable: bool,
    target_checks: Iterable[CheckResult],
    regression_checks: Iterable[CheckResult],
) -> EvaluationDecision:
    """Return a conservative result; known critical failures outrank missing evidence."""
    if not applicable:
        return EvaluationDecision(Outcome.NOT_APPLICABLE, "Experiment does not apply.", False, 0, (), ())
    if not setup_valid:
        return EvaluationDecision(Outcome.INVALID_SETUP, "Required preconditions were not met.", False, 0, (), ())

    target = tuple(target_checks)
    regressions = tuple(regression_checks)
    failed = tuple(check.name for check in regressions if check.passed is False)
    critical = tuple(
        check.name for check in regressions if check.passed is False and check.critical
    )
    target_passed = bool(target) and all(
        check.passed is True and check.error is None for check in target
    )

    if critical:
        return EvaluationDecision(
            Outcome.FAILED, "A critical regression failed.", target_passed,
            len(regressions), failed, critical
        )
    if not target:
        return EvaluationDecision(
            Outcome.INCONCLUSIVE, "No target checks were executed.", False,
            len(regressions), failed, ()
        )
    if any(check.error or check.passed is None for check in (*target, *regressions)):
        return EvaluationDecision(
            Outcome.INCONCLUSIVE, "A required check is missing or errored.",
            target_passed, len(regressions), failed, ()
        )
    if failed:
        return EvaluationDecision(
            Outcome.FAILED, "One or more regression checks failed.",
            target_passed, len(regressions), failed, ()
        )
    if not target_passed:
        return EvaluationDecision(
            Outcome.FAILED, "One or more target checks failed.", False,
            len(regressions), (), ()
        )
    if not regressions:
        return EvaluationDecision(
            Outcome.INCONCLUSIVE, "The required regression suite was empty.",
            True, 0, (), ()
        )
    return EvaluationDecision(
        Outcome.PASSED,
        "Target checks passed and regression checks completed without failures.",
        True, len(regressions), (), ()
    )
