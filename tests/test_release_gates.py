from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_release_gate_fails_on_score_and_failed_case_regression() -> None:
    dataset_name = f"release_gate_dataset_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for release gate testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    baseline_run_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "baseline",
            "prompt_version": "baseline-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by a database failover issue.",
                    "reference_answer": "The outage happened because of a database failover issue.",
                    "rubric": [
                        {
                            "name": "Root cause specificity",
                            "description": "Mentions the concrete failing component.",
                            "weight": 1.0,
                            "required_terms": ["database", "failover"],
                        }
                    ],
                }
            ],
        },
    )
    assert baseline_run_response.status_code == 201
    baseline_run_id = baseline_run_response.json()["id"]

    candidate_run_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "candidate",
            "prompt_version": "candidate-v2",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "reference_answer": "The outage happened because of a database failover issue.",
                    "rubric": [
                        {
                            "name": "Root cause specificity",
                            "description": "Mentions the concrete failing component.",
                            "weight": 1.0,
                            "required_terms": ["database", "failover"],
                        }
                    ],
                }
            ],
        },
    )
    assert candidate_run_response.status_code == 201
    candidate_run_id = candidate_run_response.json()["id"]

    gate_response = client.post(
        "/api/v1/release-gates",
        json={
            "dataset_name": dataset_name,
            "baseline_run_id": baseline_run_id,
            "candidate_run_id": candidate_run_id,
            "min_score_delta": -0.01,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 0,
        },
    )
    assert gate_response.status_code == 201
    payload = gate_response.json()
    assert payload["status"] == "failed"
    assert payload["metrics"]["score_delta"] < -0.01
    assert payload["metrics"]["failed_case_delta"] > 0
    assert any(failure["metric"] == "score_delta" for failure in payload["failures"])

    list_response = client.get("/api/v1/release-gates")
    assert list_response.status_code == 200
    assert any(decision["id"] == payload["id"] for decision in list_response.json())
