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
