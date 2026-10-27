from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_decision_endpoint_passes_complete_suite():
    response = client.post("/api/v1/evaluations/decide", json={
        "setup_valid": True, "applicable": True,
        "target_checks": [{"name": "target", "passed": True}],
        "regression_checks": [{"name": "baseline", "passed": True}],
    })
    assert response.status_code == 200
    assert response.json()["outcome"] == "passed"


def test_decision_endpoint_does_not_pass_provider_error():
    response = client.post("/api/v1/evaluations/decide", json={
        "target_checks": [{"name": "target", "passed": True}],
        "regression_checks": [{"name": "baseline", "passed": None, "error": "provider timeout"}],
    })
    assert response.status_code == 200
    assert response.json()["outcome"] == "inconclusive"
