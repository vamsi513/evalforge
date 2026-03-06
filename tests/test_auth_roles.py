from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def test_viewer_cannot_call_mutating_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(settings, "platform_api_key", "secret-key")
    monkeypatch.setattr(settings, "default_user_role", "viewer")

    headers = {"X-API-Key": "secret-key", "X-Workspace-ID": "role-viewer"}
    list_datasets = client.get("/api/v1/datasets", headers=headers)
    assert list_datasets.status_code == 200

    create_dataset = client.post(
        "/api/v1/datasets",
        headers=headers,
        json={
            "name": f"viewer_ds_{uuid4().hex[:8]}",
            "description": "Viewer should not create datasets.",
            "owner": "test-suite",
        },
    )
    assert create_dataset.status_code == 403

    compare_eval = client.post(
        "/api/v1/evals/compare",
        headers=headers,
        json={
            "dataset_name": "dummy-dataset",
            "prompt_version_a": "a",
            "prompt_version_b": "b",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize outage root cause.",
                    "candidate_a": "Database failover caused outage.",
                    "candidate_b": "Infrastructure issue caused outage.",
                    "expected_keyword": "database",
                    "reference_answer": "Database failover caused outage.",
                    "rubric": [],
                }
            ],
        },
    )
    assert compare_eval.status_code == 403


def test_editor_can_mutate_but_cannot_call_admin_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(settings, "platform_api_key", "secret-key")
    monkeypatch.setattr(settings, "default_user_role", "viewer")

    editor_headers = {
        "X-API-Key": "secret-key",
        "X-Workspace-ID": "role-editor",
        "X-User-Role": "editor",
    }
    dataset_name = f"editor_ds_{uuid4().hex[:8]}"
    create_dataset = client.post(
        "/api/v1/datasets",
        headers=editor_headers,
        json={
            "name": dataset_name,
            "description": "Editor dataset creation should succeed.",
            "owner": "test-suite",
        },
    )
    assert create_dataset.status_code == 201

    create_eval = client.post(
        "/api/v1/evals",
        headers=editor_headers,
        json={
            "dataset_name": dataset_name,
            "prompt_version": "role-v1",
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
    assert create_eval.status_code == 201

    create_evaluator = client.post(
        "/api/v1/evaluators",
        headers=editor_headers,
        json={
            "name": f"heuristic-{uuid4().hex[:6]}",
            "version": "v1",
            "kind": "heuristic",
            "status": "active",
            "description": "Editor should not be allowed to create evaluator definitions.",
            "config": {},
        },
    )
    assert create_evaluator.status_code == 403


def test_admin_can_call_admin_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(settings, "platform_api_key", "secret-key")
    monkeypatch.setattr(settings, "default_user_role", "viewer")

    admin_headers = {
        "X-API-Key": "secret-key",
        "X-Workspace-ID": "role-admin",
        "X-User-Role": "admin",
    }
    create_evaluator = client.post(
        "/api/v1/evaluators",
        headers=admin_headers,
        json={
            "name": f"admin-heuristic-{uuid4().hex[:6]}",
            "version": "v1",
            "kind": "heuristic",
            "status": "active",
            "description": "Admin can create evaluator definitions.",
            "config": {},
        },
    )
    assert create_evaluator.status_code == 201
