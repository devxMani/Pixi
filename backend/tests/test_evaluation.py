from app.domain.evaluation import CheckResult, Outcome, decide_evaluation


def test_pass_requires_target_and_nonempty_complete_regression_suite():
    result = decide_evaluation(setup_valid=True, applicable=True,
        target_checks=[CheckResult("target", True)], regression_checks=[CheckResult("baseline", True)])
    assert result.outcome == Outcome.PASSED


def test_target_failure_is_failed():
    result = decide_evaluation(setup_valid=True, applicable=True,
        target_checks=[CheckResult("target", False)], regression_checks=[CheckResult("baseline", True)])
    assert result.outcome == Outcome.FAILED


def test_critical_regression_blocks_acceptance():
    result = decide_evaluation(setup_valid=True, applicable=True,
        target_checks=[CheckResult("target", True)], regression_checks=[CheckResult("safety", False, critical=True)])
    assert result.outcome == Outcome.FAILED
    assert result.critical_regressions == ("safety",)


def test_missing_observation_is_inconclusive_not_pass():
    result = decide_evaluation(setup_valid=True, applicable=True,
        target_checks=[CheckResult("target", True)], regression_checks=[CheckResult("timeout", None, error="provider timeout")])
    assert result.outcome == Outcome.INCONCLUSIVE


def test_empty_regression_suite_is_inconclusive():
    result = decide_evaluation(setup_valid=True, applicable=True,
        target_checks=[CheckResult("target", True)], regression_checks=[])
    assert result.outcome == Outcome.INCONCLUSIVE


def test_invalid_setup_is_not_a_pass():
    result = decide_evaluation(setup_valid=False, applicable=True,
        target_checks=[CheckResult("target", True)], regression_checks=[CheckResult("baseline", True)])
    assert result.outcome == Outcome.INVALID_SETUP


def test_not_applicable_is_not_a_pass():
    result = decide_evaluation(setup_valid=True, applicable=False,
        target_checks=[CheckResult("target", True)], regression_checks=[CheckResult("baseline", True)])
    assert result.outcome == Outcome.NOT_APPLICABLE
