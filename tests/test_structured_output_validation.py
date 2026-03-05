from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_structured_output_validator_flags_missing_required_fields() -> None:
    dataset_name = f"structured_output_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for structured output validation testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    eval_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "structured-output",
            "prompt_version": "json-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Return a JSON object with summary and severity fields.",
                    "expected_keyword": "summary",
                    "candidate_output": "{\"summary\": \"Database failover issue\"}",
                    "scenario": "structured_output",
                    "slice_name": "json_response",
                    "severity": "high",
                    "required_json_fields": ["summary", "severity"],
                    "reference_answer": "{\"summary\": \"Database failover issue\", \"severity\": \"high\"}",
                    "rubric": [],
                }
            ],
        },
    )
    assert eval_response.status_code == 201
    result = eval_response.json()["results"][0]
    assert result["structured_output_valid"] is False
    assert "severity" in result["structured_output_error"]
    assert result["criterion_scores"]["structured_output"] == 0.0

    telemetry_response = client.get("/api/v1/telemetry/summary")
    assert telemetry_response.status_code == 200
    telemetry = telemetry_response.json()
    assert telemetry["structured_output_failure_count"] >= 1
