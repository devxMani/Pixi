from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 - ensures all test tables are registered
from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("APP_ENV", "development")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_project_and_scenario(client: TestClient) -> tuple[str, str]:
    project_response = client.post("/api/v1/projects", json={"name": "Demo project"})
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    scenario_response = client.post(
        f"/api/v1/projects/{project_id}/scenarios",
        json={
            "name": "Pricing answer",
            "turns": ["What does the basic plan cost?", "Does it include analytics?"],
            "assertions": [
                {"id": "mentions-price", "kind": "contains", "expected_text": "$20"},
                {"id": "latency-budget", "kind": "max_latency_ms", "threshold_ms": 1500},
                {"id": "pricing-tool", "kind": "tool_called", "tool_name": "get_pricing"},
            ],
        },
    )
    assert scenario_response.status_code == 201
    return project_id, scenario_response.json()["id"]


def test_project_scenario_demo_run_is_persisted_and_explicitly_simulated(client: TestClient):
    project_id, scenario_id = create_project_and_scenario(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/demo-runs",
        json={
            "transcript": "The basic plan costs $20 per month.",
            "latency_ms": 800,
            "tools_called": ["get_pricing"],
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "passed"
    assert run["evidence_mode"] == "simulated"
    assert run["observations"][0]["evidence_mode"] == "simulated"
    assert len(run["checks"]) == 3

    saved = client.get(f"/api/v1/runs/{run['id']}")
    assert saved.status_code == 200
    assert saved.json()["scenario_snapshot"]["name"] == "Pricing answer"
    assert saved.json()["observations"][0]["transcript"] == "The basic plan costs $20 per month."

    history = client.get(f"/api/v1/projects/{project_id}/runs")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == run["id"]
    assert history.json()[0]["evidence_mode"] == "simulated"


def test_fixture_provider_error_is_saved_as_inconclusive(client: TestClient):
    project_id, scenario_id = create_project_and_scenario(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/demo-runs",
        json={"error": "fixture timeout"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "inconclusive"
    assert response.json()["observations"][0]["error"] == "fixture timeout"
    assert all(check["passed"] is None for check in response.json()["checks"])


def test_project_scoping_returns_404_for_unknown_or_wrong_scenario(client: TestClient):
    project_id, scenario_id = create_project_and_scenario(client)
    response = client.post(
        f"/api/v1/projects/not-a-project/scenarios/{scenario_id}/demo-runs",
        json={"transcript": "irrelevant"},
    )
    assert response.status_code == 404
    assert client.get("/api/v1/projects/not-a-project/scenarios").status_code == 404
    assert client.get(f"/api/v1/projects/{project_id}/scenarios").status_code == 200


def test_api_is_disabled_outside_development(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    response = client.get("/api/v1/projects")
    assert response.status_code == 503


def test_browser_entrypoints_are_served_by_the_api(client: TestClient):
    prototype = client.get("/")
    console = client.get("/console.html")
    assert prototype.status_code == 200
    assert "Talk to Miso" in prototype.text
    assert console.status_code == 200
    assert "Reliability Workspace" in console.text



def create_candidate(client: TestClient, project_id: str, scenario_id: str) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/candidates",
        json={
            "scenario_id": scenario_id,
            "hypothesis": "Shorter confirmations reduce waiting without reducing accuracy.",
            "proposed_change": "Use a one-sentence confirmation for the common path.",
        },
    )
    assert response.status_code == 201
    assert response.json()["production_applied"] is False
    return response.json()["id"]


def test_simulated_candidate_cannot_be_approved_for_release(client: TestClient):
    project_id, scenario_id = create_project_and_scenario(client)
    candidate_id = create_candidate(client, project_id, scenario_id)
    evaluation = client.post(
        f"/api/v1/candidates/{candidate_id}/evaluate",
        json={
            "target_checks": [{"name": "target", "passed": True}],
            "regression_checks": [{"name": "baseline", "passed": True}],
        },
    )
    assert evaluation.status_code == 201
    assert evaluation.json()["latest_evaluation"]["outcome"] == "passed"
    assert evaluation.json()["latest_evaluation"]["evidence_mode"] == "simulated"
    approval = client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"decision": "accept", "reviewer": "Reviewer"},
    )
    assert approval.status_code == 409
    assert "Simulated evidence" in approval.json()["detail"]
    rejected = client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"decision": "reject", "reviewer": "Reviewer"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["production_applied"] is False


def test_critical_failure_blocks_candidate_even_with_missing_evidence(client: TestClient):
    project_id, scenario_id = create_project_and_scenario(client)
    candidate_id = create_candidate(client, project_id, scenario_id)
    evaluation = client.post(
        f"/api/v1/candidates/{candidate_id}/evaluate",
        json={
            "target_checks": [{"name": "target", "passed": True}],
            "regression_checks": [
                {"name": "missing", "passed": None, "error": "timeout"},
                {"name": "safety", "passed": False, "critical": True},
            ],
        },
    )
    assert evaluation.status_code == 201
    assert evaluation.json()["latest_evaluation"]["outcome"] == "failed"
    assert evaluation.json()["latest_evaluation"]["critical_regressions"] == ["safety"]


def test_empty_candidate_regression_suite_is_inconclusive(client: TestClient):
    project_id, scenario_id = create_project_and_scenario(client)
    candidate_id = create_candidate(client, project_id, scenario_id)
    evaluation = client.post(
        f"/api/v1/candidates/{candidate_id}/evaluate",
        json={
            "target_checks": [{"name": "target", "passed": True}],
            "regression_checks": [],
        },
    )
    assert evaluation.status_code == 201
    assert evaluation.json()["latest_evaluation"]["outcome"] == "inconclusive"
