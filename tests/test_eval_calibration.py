from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_judge_eval_includes_groundedness_signals() -> None:
    dataset_name = f"judge_ground_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for judge groundedness enrichment testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    response = client.post(
        "/api/v1/evals/judge",
        json={
            "dataset_name": dataset_name,
            "prompt_version": "judge-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize outage cause.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by a database issue and malware corruption.",
                    "reference_answer": "The outage was caused by a database issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert response.status_code == 201
    result = response.json()["results"][0]
    assert "groundedness_score" in result
    assert result["groundedness_score"] < 1.0
    assert "unsupported_terms" in result
    assert "malware" in result["unsupported_terms"]


def test_eval_calibration_report_returns_bins() -> None:
    dataset_name = f"calibration_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for calibration report testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    for idx, candidate_output in enumerate(
        [
            "The outage was caused by a database failover issue.",
            "The outage was caused by an infrastructure issue.",
            "Database failover caused the outage.",
        ]
    ):
        eval_response = client.post(
            "/api/v1/evals",
            json={
                "dataset_name": dataset_name,
                "experiment_name": "calibration-track",
                "prompt_version": f"v{idx + 1}",
                "model_name": "gpt-4o-mini",
                "samples": [
                    {
                        "prompt": "Summarize outage cause in one sentence.",
                        "expected_keyword": "database",
                        "candidate_output": candidate_output,
                        "reference_answer": "The outage was caused by a database failover issue.",
                        "rubric": [],
                    }
                ],
            },
        )
        assert eval_response.status_code == 201

    calibration = client.get(
        "/api/v1/evals/calibration",
        params={
            "dataset_name": dataset_name,
            "experiment_name": "calibration-track",
            "lookback_runs": 10,
            "bin_count": 5,
        },
    )
    assert calibration.status_code == 200
    payload = calibration.json()
    assert payload["total_cases"] >= 3
    assert 0.0 <= payload["expected_calibration_error"] <= 1.0
    assert 0.0 <= payload["brier_score"] <= 1.0
    assert payload["bins"]
