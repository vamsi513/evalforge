from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def test_api_key_and_workspace_scoping(monkeypatch) -> None:
    monkeypatch.setattr(settings, "platform_api_key", "secret-key")

    unauthorized_response = client.get("/api/v1/datasets")
    assert unauthorized_response.status_code == 401

    headers_a = {
        "X-API-Key": "secret-key",
        "X-Workspace-ID": "team-a",
        "X-User-Role": "editor",
    }
    headers_b = {
        "X-API-Key": "secret-key",
        "X-Workspace-ID": "team-b",
        "X-User-Role": "editor",
    }

    dataset_a = f"workspace_a_{uuid4().hex[:8]}"
    dataset_b = f"workspace_b_{uuid4().hex[:8]}"

    create_a = client.post(
        "/api/v1/datasets",
        headers=headers_a,
        json={
            "name": dataset_a,
            "description": "Workspace A dataset for auth scoping.",
            "owner": "test-suite",
        },
    )
    assert create_a.status_code == 201
    assert create_a.json()["workspace_id"] == "team-a"

    create_b = client.post(
        "/api/v1/datasets",
        headers=headers_b,
        json={
            "name": dataset_b,
            "description": "Workspace B dataset for auth scoping.",
            "owner": "test-suite",
        },
    )
    assert create_b.status_code == 201
    assert create_b.json()["workspace_id"] == "team-b"

    list_a = client.get("/api/v1/datasets", headers=headers_a)
    assert list_a.status_code == 200
    names_a = {dataset["name"] for dataset in list_a.json()}
    assert dataset_a in names_a
    assert dataset_b not in names_a

    create_run_a = client.post(
        "/api/v1/evals",
        headers=headers_a,
        json={
            "dataset_name": dataset_a,
            "prompt_version": "workspace-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by a database failover issue.",
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert create_run_a.status_code == 201
    assert create_run_a.json()["workspace_id"] == "team-a"

    list_runs_b = client.get("/api/v1/evals", headers=headers_b)
    assert list_runs_b.status_code == 200
    assert all(run["workspace_id"] == "team-b" for run in list_runs_b.json())
