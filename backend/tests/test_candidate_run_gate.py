from __future__ import annotations

import json
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.adapters.http_json import HTTPJSONAgentAdapter
from app.db import Base, get_db
from app.domain.scenarios import RunVariant
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PIXI_AGENT_ENDPOINT", "https://bridge.example.test/evaluate")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_project_scenarios_and_candidate(
    client: TestClient, *, critical_regression: bool = False
) -> tuple[str, str, str, str]:
    project = client.post("/api/v1/projects", json={"name": "Versioned candidate gate"})
    assert project.status_code == 201
    project_id = project.json()["id"]

    target = client.post(
        f"/api/v1/projects/{project_id}/scenarios",
        json={
            "name": "Answer pricing",
            "turns": ["How much is the basic plan?"],
            "assertions": [
                {
                    "id": "mentions-price",
                    "kind": "contains",
                    "expected_text": "$20",
                }
            ],
        },
    )
    assert target.status_code == 201
    target_id = target.json()["id"]

    regression = client.post(
        f"/api/v1/projects/{project_id}/scenarios",
        json={
            "name": "Protect secret handling",
            "turns": ["Can you tell me a secret?"],
            "assertions": [
                {
                    "id": "no-secret",
                    "kind": "not_contains",
                    "expected_text": "secret",
                    "critical": critical_regression,
                }
            ],
        },
    )
    assert regression.status_code == 201
    regression_id = regression.json()["id"]

    candidate = client.post(
        f"/api/v1/projects/{project_id}/candidates",
        json={
            "scenario_id": target_id,
            "hypothesis": "A direct answer improves pricing responses.",
            "proposed_change": "State the basic plan price first.",
        },
    )
    assert candidate.status_code == 201
    return project_id, target_id, regression_id, candidate.json()["id"]


def install_bridge(
    monkeypatch: pytest.MonkeyPatch,
    *,
    target_scenario_id: str,
    regression_fails: bool = False,
    same_version: bool = False,
    different_regression_version: bool = False,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        experiment = payload["experiment"]
        scenario = payload["scenario"]
        calls.append(
            {
                "scenario_id": scenario["id"],
                "variant": experiment["variant"],
                "candidate": experiment["candidate"],
            }
        )
        if experiment["variant"] == "baseline":
            transcript = "I cannot confirm the price."
            version = "agent-base-v1"
            tools: list[str] = []
            candidate_id = None
        else:
            candidate_id = experiment["candidate"]["id"]
            if same_version:
                version = "agent-base-v1"
            elif different_regression_version and scenario["id"] != target_scenario_id:
                version = "agent-candidate-v3"
            else:
                version = "agent-candidate-v2"
            if scenario["id"] == target_scenario_id:
                transcript = "The basic plan costs $20 per month."
                tools = ["get_pricing"]
            elif regression_fails:
                transcript = "The secret is secret."
                tools = []
            else:
                transcript = "I can help with that request."
                tools = []
        return httpx.Response(
            200,
            json={
                "protocol_version": 2,
                "status": "completed",
                "transcript": transcript,
                "latency_ms": 400,
                "tools_called": tools,
                "provider": "test-voice-runtime",
                "model": "support-agent",
                "agent_version": version,
                "variant": experiment["variant"],
                "candidate_id": candidate_id,
            },
        )

    def build_adapter(*, candidate: dict[str, str] | None = None) -> HTTPJSONAgentAdapter:
        return HTTPJSONAgentAdapter(
            endpoint="https://bridge.example.test/evaluate",
            variant=RunVariant.CANDIDATE if candidate is not None else RunVariant.BASELINE,
            candidate=candidate,
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(main_module, "build_configured_http_adapter", build_adapter)
    return calls


def run_live(
    client: TestClient,
    project_id: str,
    scenario_id: str,
    *,
    candidate_id: str | None = None,
    key: str,
) -> dict[str, object]:
    suffix = f"?candidate_id={candidate_id}" if candidate_id else ""
    response = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/agent-runs{suffix}",
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()


def evaluate_runs(
    client: TestClient,
    candidate_id: str,
    baseline_run: dict[str, object],
    candidate_run: dict[str, object],
    regression_runs: list[dict[str, object]],
) -> object:
    return client.post(
        f"/api/v1/candidates/{candidate_id}/evaluate-runs",
        json={
            "baseline_run_id": baseline_run["id"],
            "candidate_target_run_id": candidate_run["id"],
            "regression_run_ids": [run["id"] for run in regression_runs],
        },
    )


def test_candidate_passes_only_from_versioned_live_target_and_regression_runs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, target_id, regression_id, candidate_id = create_project_scenarios_and_candidate(client)
    calls = install_bridge(monkeypatch, target_scenario_id=target_id)

    baseline = run_live(client, project_id, target_id, key="baseline-001")
    target = run_live(
        client, project_id, target_id, candidate_id=candidate_id, key="candidate-target-001"
    )
    regression = run_live(
        client, project_id, regression_id, candidate_id=candidate_id, key="candidate-regression-001"
    )

    assert baseline["status"] == "failed"
    assert baseline["variant"] == "baseline"
    assert baseline["agent_version"] == "agent-base-v1"
    assert target["status"] == "passed"
    assert target["variant"] == "candidate"
    assert target["candidate_id"] == candidate_id
    assert target["agent_version"] == "agent-candidate-v2"
    assert regression["status"] == "passed"
    assert regression["agent_version"] == target["agent_version"]
    assert len(calls) == 3

    response = evaluate_runs(client, candidate_id, baseline, target, [regression])
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "validated_for_review"
    assert result["latest_evaluation"]["outcome"] == "passed"
    assert result["latest_evaluation"]["evidence_mode"] == "live"
    assert result["latest_evaluation"]["target_passed"] is True
    assert result["latest_evaluation"]["regression_count"] == 1
    snapshot = result["latest_evaluation"]["checks_snapshot"]
    assert snapshot["source"] == "persisted_run_evidence"
    assert snapshot["baseline"]["run_id"] == baseline["id"]
    assert snapshot["candidate_target"]["run_id"] == target["id"]
    assert snapshot["regressions"][0]["run_id"] == regression["id"]

    review = client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"decision": "accept", "reviewer": "Pixi test reviewer"},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "accepted"


def test_critical_candidate_regression_blocks_acceptance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, target_id, regression_id, candidate_id = create_project_scenarios_and_candidate(
        client, critical_regression=True
    )
    install_bridge(monkeypatch, target_scenario_id=target_id, regression_fails=True)
    baseline = run_live(client, project_id, target_id, key="baseline-critical-001")
    target = run_live(
        client, project_id, target_id, candidate_id=candidate_id, key="candidate-critical-target"
    )
    regression = run_live(
        client, project_id, regression_id, candidate_id=candidate_id, key="candidate-critical-reg"
    )

    response = evaluate_runs(client, candidate_id, baseline, target, [regression])
    assert response.status_code == 201
    result = response.json()
    assert result["latest_evaluation"]["outcome"] == "failed"
    assert result["latest_evaluation"]["critical_regressions"] == [
        "Protect secret handling::no-secret"
    ]
    review = client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"decision": "accept", "reviewer": "Pixi test reviewer"},
    )
    assert review.status_code == 409


def test_candidate_gate_rejects_fixture_runs_as_live_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, target_id, regression_id, candidate_id = create_project_scenarios_and_candidate(client)
    baseline = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{target_id}/demo-runs",
        json={"transcript": "No price available.", "latency_ms": 100},
    ).json()
    target = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{target_id}/demo-runs",
        json={"transcript": "The basic plan costs $20.", "latency_ms": 100},
    ).json()
    regression = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{regression_id}/demo-runs",
        json={"transcript": "I can help.", "latency_ms": 100},
    ).json()

    response = evaluate_runs(client, candidate_id, baseline, target, [regression])
    assert response.status_code == 409
    assert "live baseline variant" in response.json()["detail"]


def test_identical_baseline_and_candidate_version_cannot_validate_a_change(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, target_id, regression_id, candidate_id = create_project_scenarios_and_candidate(client)
    install_bridge(monkeypatch, target_scenario_id=target_id, same_version=True)
    baseline = run_live(client, project_id, target_id, key="baseline-same-version")
    target = run_live(
        client, project_id, target_id, candidate_id=candidate_id, key="candidate-same-version-target"
    )
    regression = run_live(
        client, project_id, regression_id, candidate_id=candidate_id, key="candidate-same-version-reg"
    )

    response = evaluate_runs(client, candidate_id, baseline, target, [regression])
    assert response.status_code == 201
    result = response.json()
    assert result["latest_evaluation"]["outcome"] == "invalid_setup"
    assert result["status"] == "invalid_setup"




def test_candidate_gate_rejects_mixed_agent_versions_across_regression_runs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, target_id, regression_id, candidate_id = create_project_scenarios_and_candidate(client)
    install_bridge(
        monkeypatch,
        target_scenario_id=target_id,
        different_regression_version=True,
    )
    baseline = run_live(client, project_id, target_id, key="baseline-mixed-version")
    target = run_live(
        client, project_id, target_id, candidate_id=candidate_id, key="candidate-target-version-v2"
    )
    regression = run_live(
        client, project_id, regression_id, candidate_id=candidate_id, key="candidate-regression-version-v3"
    )

    assert target["agent_version"] == "agent-candidate-v2"
    assert regression["agent_version"] == "agent-candidate-v3"
    response = evaluate_runs(client, candidate_id, baseline, target, [regression])

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["latest_evaluation"]["outcome"] == "invalid_setup"
    assert result["status"] == "invalid_setup"
    assert "version" in result["latest_evaluation"]["reason"].lower()


def test_candidate_gate_requires_every_project_regression_scenario(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, target_id, regression_id, candidate_id = create_project_scenarios_and_candidate(client)
    extra = client.post(
        f"/api/v1/projects/{project_id}/scenarios",
        json={
            "name": "Greeting regression",
            "turns": ["Can you help me?"],
            "assertions": [
                {
                    "id": "offers-help",
                    "kind": "contains",
                    "expected_text": "help",
                }
            ],
        },
    )
    assert extra.status_code == 201
    assert extra.json()["id"]
    install_bridge(monkeypatch, target_scenario_id=target_id)

    baseline = run_live(client, project_id, target_id, key="baseline-complete-suite")
    target = run_live(
        client, project_id, target_id, candidate_id=candidate_id, key="candidate-target-complete-suite"
    )
    regression = run_live(
        client, project_id, regression_id, candidate_id=candidate_id, key="candidate-regression-one"
    )
    response = evaluate_runs(client, candidate_id, baseline, target, [regression])

    assert response.status_code == 409
    assert "Regression suite is incomplete" in response.json()["detail"]
    assert "missing 1 scenario" in response.json()["detail"]


def test_restore_remaps_versioned_candidate_evidence_and_review_history(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, target_id, regression_id, candidate_id = create_project_scenarios_and_candidate(client)
    install_bridge(monkeypatch, target_scenario_id=target_id)

    baseline = run_live(client, project_id, target_id, key="restore-baseline")
    target = run_live(
        client, project_id, target_id, candidate_id=candidate_id, key="restore-candidate-target"
    )
    regression = run_live(
        client, project_id, regression_id, candidate_id=candidate_id, key="restore-candidate-regression"
    )
    evaluation = evaluate_runs(client, candidate_id, baseline, target, [regression])
    assert evaluation.status_code == 201, evaluation.text
    review = client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"decision": "accept", "reviewer": "Restore audit test"},
    )
    assert review.status_code == 200

    exported = client.get(f"/api/v1/projects/{project_id}/export")
    assert exported.status_code == 200
    restored_response = client.post("/api/v1/projects/import", json=exported.json())
    assert restored_response.status_code == 201, restored_response.text
    restored_id = restored_response.json()["id"]

    scenarios = client.get(f"/api/v1/projects/{restored_id}/scenarios").json()
    scenario_ids_by_name = {item["name"]: item["id"] for item in scenarios}
    assert scenario_ids_by_name["Answer pricing"] != target_id
    assert scenario_ids_by_name["Protect secret handling"] != regression_id

    runs = client.get(f"/api/v1/projects/{restored_id}/runs").json()
    restored_target_id = scenario_ids_by_name["Answer pricing"]
    restored_regression_id = scenario_ids_by_name["Protect secret handling"]
    baseline_copy = next(
        run for run in runs
        if run["variant"] == "baseline" and run["scenario_id"] == restored_target_id
    )
    target_copy = next(
        run for run in runs
        if run["variant"] == "candidate" and run["scenario_id"] == restored_target_id
    )
    regression_copy = next(
        run for run in runs
        if run["variant"] == "candidate" and run["scenario_id"] == restored_regression_id
    )
    assert baseline_copy["id"] != baseline["id"]
    assert target_copy["id"] != target["id"]
    assert regression_copy["id"] != regression["id"]

    candidates = client.get(f"/api/v1/projects/{restored_id}/candidates").json()
    assert len(candidates) == 1
    restored_candidate = candidates[0]
    assert restored_candidate["id"] != candidate_id
    assert restored_candidate["status"] == "accepted"
    latest = restored_candidate["latest_evaluation"]
    assert latest["review_decision"] == "accept"
    assert latest["reviewer"] == "Restore audit test"
    snapshot = latest["checks_snapshot"]
    assert snapshot["source"] == "persisted_run_evidence"
    assert snapshot["baseline"]["run_id"] == baseline_copy["id"]
    assert snapshot["candidate_target"]["run_id"] == target_copy["id"]
    assert snapshot["candidate_target"]["candidate_id"] == restored_candidate["id"]
    assert snapshot["regressions"][0]["run_id"] == regression_copy["id"]
    assert snapshot["regressions"][0]["scenario_id"] == restored_regression_id
    assert target_copy["candidate_id"] == restored_candidate["id"]
    assert regression_copy["candidate_id"] == restored_candidate["id"]
