from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_groundedness_validator_flags_unsupported_terms() -> None:
    dataset_name = f"groundedness_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for groundedness validation testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    eval_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "groundedness-checks",
            "prompt_version": "facts-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by a database failover issue and malware corruption.",
                    "scenario": "factuality",
                    "slice_name": "unsupported_claims",
                    "severity": "high",
                    "required_json_fields": [],
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert eval_response.status_code == 201
    result = eval_response.json()["results"][0]
    assert result["groundedness_score"] < 0.5
    assert "malware" in result["unsupported_terms"]
    assert result["criterion_scores"]["groundedness"] < 0.5

    telemetry_response = client.get("/api/v1/telemetry/summary")
    assert telemetry_response.status_code == 200
    telemetry = telemetry_response.json()
    assert telemetry["groundedness_failure_count"] >= 1
