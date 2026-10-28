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
    project = client.post("/api/v1/projects", json={"name": "Live bridge test"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    scenario = client.post(
        f"/api/v1/projects/{project_id}/scenarios",
        json={
            "name": "Answer pricing",
            "turns": ["How much is the basic plan?"],
            "assertions": [
                {
                    "id": "mentions-price",
                    "kind": "contains",
                    "expected_text": "$20",
                },
                {
                    "id": "pricing-tool",
                    "kind": "tool_called",
                    "tool_name": "get_pricing",
                },
            ],
        },
    )
    assert scenario.status_code == 201
    return project_id, scenario.json()["id"]


def test_agent_run_persists_live_evidence_and_replays_idempotently(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, scenario_id = create_project_and_scenario(client)
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["protocol_version"] == 2
        assert body["experiment"] == {"variant": "baseline", "candidate": None}
        assert body["scenario"]["id"] == scenario_id
        return httpx.Response(
            200,
            json={
                "protocol_version": 2,
                "status": "completed",
                "transcript": "The basic plan costs $20 per month.",
                "latency_ms": 510,
                "tools_called": ["get_pricing"],
                "provider": "mocked-live-agent",
                "model": "voice-agent-v1",
                "agent_version": "agent-base-v1",
                "variant": "baseline",
                "candidate_id": None,
                "voice_trace": {
                    "status": "completed",
                    "error": None,
                    "input_mode": "text",
                    "latency_basis": "text_input_to_completed_response",
                    "agent_version": "agent-base-v1",
                    "candidate_id": None,
                    "measured_turn_count": 1,
                    "scenario_elapsed_ms": 510.0,
                    "turns": [
                        {
                            "user_input": "How much is the basic plan?",
                            "assistant_output": "The basic plan costs $20 per month.",
                            "tools": [
                                {
                                    "name": "get_pricing",
                                    "arguments": {"plan": "basic"},
                                    "output": "$20 per month",
                                    "latency_ms": 8.5,
                                    "success": True,
                                    "error": None,
                                }
                            ],
                            "latency": {
                                "stt_processing_ms": None,
                                "eot_latency_ms": None,
                                "llm_ttft_ms": 140.0,
                                "tts_ttfb_ms": 90.0,
                                "e2e_ms": 325.0,
                            },
                            "interruption": {
                                "interrupted": False,
                                "overlapping_speech": False,
                                "false_interruption": False,
                                "detection_delay_ms": None,
                                "agent_speech_duration_ms": None,
                                "recovered": False,
                            },
                            "interrupted": False,
                            "status": "completed",
                            "error": None,
                        }
                    ],
                },
            },
        )

    monkeypatch.setattr(
        main_module,
        "build_configured_http_adapter",
        lambda candidate=None: HTTPJSONAgentAdapter(
            endpoint="https://bridge.example.test/evaluate",
            api_key="test-secret",
            variant=RunVariant.CANDIDATE if candidate else RunVariant.BASELINE,
            candidate=candidate,
            transport=httpx.MockTransport(handler),
        ),
    )
    url = (
        f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/agent-runs"
    )
    headers = {"Idempotency-Key": "live-call-001"}

    first = client.post(url, headers=headers)
    replay = client.post(url, headers=headers)

    assert first.status_code == 201
    run = first.json()
    assert run["status"] == "passed"
    assert run["evidence_mode"] == "live"
    assert run["variant"] == "baseline"
    assert run["agent_version"] == "agent-base-v1"
    assert run["adapter_name"] == "http-json-bridge"
    assert run["observations"][0]["evidence_mode"] == "live"
    assert run["observations"][0]["provider"] == "mocked-live-agent"
    assert run["observations"][0]["model"] == "voice-agent-v1"
    assert run["observations"][0]["voice_trace"]["input_mode"] == "text"
    assert run["observations"][0]["voice_trace"]["turns"][0]["tools"][0]["name"] == "get_pricing"
    assert run["observations"][0]["voice_trace"]["turns"][0]["latency"]["llm_ttft_ms"] == 140.0
    assert run["checks"] and all(check["passed"] is True for check in run["checks"])
    assert replay.status_code == 200
    assert replay.json()["id"] == run["id"]
    assert calls == 1

    history = client.get(f"/api/v1/projects/{project_id}/runs")
    assert history.status_code == 200
    assert len(history.json()) == 1

    # Structured trace survives the user-initiated JSON backup and restore path.
    backup_response = client.get(f"/api/v1/projects/{project_id}/export")
    assert backup_response.status_code == 200
    backup = backup_response.json()
    assert backup["runs"][0]["observations"][0]["voice_trace"]["agent_version"] == "agent-base-v1"

    restored = client.post("/api/v1/projects/import", json=backup)
    assert restored.status_code == 201
    restored_project_id = restored.json()["id"]
    assert restored_project_id != project_id
    restored_history = client.get(f"/api/v1/projects/{restored_project_id}/runs")
    assert restored_history.status_code == 200
    assert restored_history.json()[0]["observations"][0]["voice_trace"]["turns"][0]["tools"][0]["latency_ms"] == 8.5


def test_agent_run_requires_server_side_endpoint_configuration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, scenario_id = create_project_and_scenario(client)
    monkeypatch.setenv("PIXI_AGENT_ENDPOINT", "")
    response = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/agent-runs"
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_invalid_bridge_response_is_saved_as_inconclusive_not_passed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, scenario_id = create_project_and_scenario(client)
    monkeypatch.setattr(
        main_module,
        "build_configured_http_adapter",
        lambda candidate=None: HTTPJSONAgentAdapter(
            endpoint="https://bridge.example.test/evaluate",
            variant=RunVariant.CANDIDATE if candidate else RunVariant.BASELINE,
            candidate=candidate,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "protocol_version": 99,
                        "status": "completed",
                        "transcript": "The basic plan costs $20.",
                        "tools_called": ["get_pricing"],
                    },
                )
            ),
        ),
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/agent-runs"
    )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "inconclusive"
    assert all(check["passed"] is None for check in run["checks"])
    assert "did not match protocol version 2" in run["observations"][0]["error"]
