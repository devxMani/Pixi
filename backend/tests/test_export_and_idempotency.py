"""API integration coverage for durable project exports and idempotent run creation."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Use an isolated in-memory database for every API test."""
    monkeypatch.setenv("APP_ENV", "development")
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


def create_project_and_scenario(client: TestClient) -> tuple[str, str]:
    project_response = client.post("/api/v1/projects", json={"name": "Export test project"})
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    scenario_response = client.post(
        f"/api/v1/projects/{project_id}/scenarios",
        json={
            "name": "Pricing question",
            "turns": ["How much does the basic plan cost?"],
            "assertions": [
                {
                    "id": "mentions-price",
                    "kind": "contains",
                    "expected_text": "$20",
                }
            ],
        },
    )
    assert scenario_response.status_code == 201
    return project_id, scenario_response.json()["id"]


def test_project_export_includes_scenarios_runs_observations_and_candidate_history(
    client: TestClient,
) -> None:
    project_id, scenario_id = create_project_and_scenario(client)
    run_response = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/demo-runs",
        headers={"Idempotency-Key": "export-seed-run"},
        json={"transcript": "The basic plan costs $20 per month.", "latency_ms": 500},
    )
    assert run_response.status_code == 201

    candidate_response = client.post(
        f"/api/v1/projects/{project_id}/candidates",
        json={
            "scenario_id": scenario_id,
            "hypothesis": "A clearer pricing answer should pass the target scenario.",
            "proposed_change": "State the monthly price directly.",
        },
    )
    assert candidate_response.status_code == 201
    candidate_id = candidate_response.json()["id"]
    evaluation_response = client.post(
        f"/api/v1/candidates/{candidate_id}/evaluate",
        json={
            "setup_valid": True,
            "applicable": True,
            "target_checks": [{"name": "target-pricing", "passed": True}],
            "regression_checks": [{"name": "safety-baseline", "passed": True}],
        },
    )
    assert evaluation_response.status_code == 201

    response = client.get(f"/api/v1/projects/{project_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert f'pixi-project-{project_id}.json' in response.headers["content-disposition"]

    snapshot = response.json()
    assert snapshot["schema_version"] == 1
    assert snapshot["project"]["id"] == project_id
    assert len(snapshot["scenarios"]) == 1
    assert snapshot["scenarios"][0]["id"] == scenario_id
    assert len(snapshot["runs"]) == 1
    assert snapshot["runs"][0]["evidence_mode"] == "simulated"
    assert snapshot["runs"][0]["observations"][0]["transcript"] == (
        "The basic plan costs $20 per month."
    )
    assert snapshot["runs"][0]["checks"][0]["assertion_id"] == "mentions-price"
    assert len(snapshot["candidates"]) == 1
    assert snapshot["candidates"][0]["evaluations"][0]["outcome"] == "passed"
    assert snapshot["candidates"][0]["evaluations"][0]["evidence_mode"] == "simulated"

    restored_response = client.post(
        "/api/v1/projects/import",
        json={**snapshot, "name_override": "Recovery copy"},
    )
    assert restored_response.status_code == 201, restored_response.text
    restored = restored_response.json()
    restored_project_id = restored["id"]
    assert restored_project_id != project_id
    assert restored["restored_from"] == project_id
    assert restored["name"] == "Recovery copy"
    assert restored["counts"] == {
        "scenarios": 1,
        "runs": 1,
        "candidates": 1,
        "evaluations": 1,
    }

    restored_scenarios = client.get(
        f"/api/v1/projects/{restored_project_id}/scenarios"
    ).json()
    restored_runs = client.get(f"/api/v1/projects/{restored_project_id}/runs").json()
    restored_candidates = client.get(
        f"/api/v1/projects/{restored_project_id}/candidates"
    ).json()
    assert len(restored_scenarios) == len(restored_runs) == len(restored_candidates) == 1

    restored_scenario_id = restored_scenarios[0]["id"]
    restored_run = restored_runs[0]
    restored_candidate = restored_candidates[0]
    assert restored_scenario_id != scenario_id
    assert restored_scenario_id == restored_run["scenario_id"]
    assert restored_run["id"] != run_response.json()["id"]
    assert restored_run["scenario_snapshot"]["id"] == restored_scenario_id
    assert restored_run["observations"][0]["transcript"] == (
        "The basic plan costs $20 per month."
    )
    assert restored_candidate["id"] != candidate_id
    assert restored_candidate["scenario_id"] == restored_scenario_id
    assert restored_candidate["latest_evaluation"]["outcome"] == "passed"
    assert restored_candidate["latest_evaluation"]["evidence_mode"] == "simulated"

    # Restore creates a second project copy; it does not overwrite the source.
    original_runs = client.get(f"/api/v1/projects/{project_id}/runs").json()
    assert len(original_runs) == 1
    assert original_runs[0]["id"] == run_response.json()["id"]


def test_project_export_returns_404_for_unknown_project(client: TestClient) -> None:
    response = client.get("/api/v1/projects/project-that-does-not-exist/export")
    assert response.status_code == 404


def test_idempotency_key_replays_same_run_and_rejects_changed_payload(
    client: TestClient,
) -> None:
    project_id, scenario_id = create_project_and_scenario(client)
    url = f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/demo-runs"
    headers = {"Idempotency-Key": "same-attempt-001"}
    payload = {"transcript": "The plan costs $20.", "latency_ms": 420}

    first = client.post(url, headers=headers, json=payload)
    replay = client.post(url, headers=headers, json=payload)
    changed = client.post(
        url,
        headers=headers,
        json={"transcript": "The plan costs $30.", "latency_ms": 420},
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert changed.status_code == 409
    assert "different request payload" in changed.json()["detail"]

    history = client.get(f"/api/v1/projects/{project_id}/runs")
    assert history.status_code == 200
    assert len(history.json()) == 1
