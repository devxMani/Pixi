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
            version = "agent-base-v1" if same_version else "agent-candidate-v2"
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
