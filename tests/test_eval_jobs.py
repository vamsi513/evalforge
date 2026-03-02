from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_async_eval_job_lifecycle() -> None:
    dataset_name = f"test_dataset_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for async job lifecycle testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    create_job_response = client.post(
        "/api/v1/evals/async",
        json={
            "dataset_name": dataset_name,
            "prompt_version": "async-test-v1",
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
    assert create_job_response.status_code == 202
    job_id = create_job_response.json()["id"]

    get_job_response = client.get(f"/api/v1/evals/jobs/{job_id}")
    assert get_job_response.status_code == 200
    assert get_job_response.json()["status"] == "completed"
    assert get_job_response.json()["result"]["dataset_name"] == dataset_name

    list_jobs_response = client.get("/api/v1/evals/jobs")
    assert list_jobs_response.status_code == 200
    assert any(job["id"] == job_id for job in list_jobs_response.json())
