from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_telemetry_summary_includes_experiment_and_use_case_rollups() -> None:
    dataset_name = f"telemetry_rollup_{uuid4().hex[:8]}"
    experiment_name = f"rollup-exp-{uuid4().hex[:6]}"
    use_case_name = f"rollup_use_case_{uuid4().hex[:6]}"

    create_dataset = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for telemetry rollup testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset.status_code == 201

    create_eval = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "rollup-v1",
            "model_name": "gpt-4o-mini",
            "run_metadata": {"use_case": use_case_name},
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

    telemetry_response = client.get("/api/v1/telemetry/summary")
    assert telemetry_response.status_code == 200
    payload = telemetry_response.json()

    experiment_keys = {item["key"] for item in payload["experiment_rollups"]}
    use_case_keys = {item["key"] for item in payload["use_case_rollups"]}

    assert experiment_name in experiment_keys
    assert use_case_name in use_case_keys

