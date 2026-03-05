from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_evaluator_registry_exposes_default_builtins() -> None:
    response = client.get("/api/v1/evaluators")
    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload}
    versions = {item["version"] for item in payload}

    assert {"keyword", "reference_overlap", "rubric", "structured_output", "groundedness"} <= names
    assert "heuristic-v1" in versions
    assert all(item["status"] == "active" for item in payload)

