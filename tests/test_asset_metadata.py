from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_golden_case_preserves_scenario_metadata_in_bundle_export() -> None:
    dataset_name = f"asset_metadata_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for scenario metadata testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    create_case_response = client.post(
        "/api/v1/assets/golden-cases",
        json={
            "dataset_name": dataset_name,
            "input_prompt": "Summarize the outage root cause in one sentence.",
            "expected_keyword": "database",
            "reference_answer": "The outage happened because of a database failover issue.",
            "scenario": "incident_summary",
            "slice_name": "database_failover",
            "severity": "high",
            "rubric": [
                {
                    "name": "Root cause specificity",
                    "description": "Mentions the concrete failing component.",
                    "weight": 1.0,
                    "required_terms": ["database", "failover"],
                }
            ],
            "tags": ["incident", "summary"],
        },
    )
    assert create_case_response.status_code == 201

    export_response = client.get(f"/api/v1/assets/bundles/{dataset_name}")
    assert export_response.status_code == 200
    case = export_response.json()["golden_cases"][0]
    assert case["scenario"] == "incident_summary"
    assert case["slice_name"] == "database_failover"
    assert case["severity"] == "high"
