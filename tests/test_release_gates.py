from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.release_gate_service import release_gate_service


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
    assert payload["metrics"]["scenario_metrics"][0]["scenario"] == "general"
    assert any(failure["metric"] == "score_delta" for failure in payload["failures"])
    assert any(failure["code"] == "SCORE_DELTA_FAIL" for failure in payload["failures"])

    list_response = client.get("/api/v1/release-gates")
    assert list_response.status_code == 200
    assert any(decision["id"] == payload["id"] for decision in list_response.json())


def test_release_gate_reports_scenario_level_regression() -> None:
    dataset_name = f"release_gate_scenario_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for scenario regression testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    baseline_run_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "baseline-scenario",
            "prompt_version": "baseline-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by a database failover issue.",
                    "scenario": "incident_summary",
                    "slice_name": "database_failover",
                    "severity": "high",
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

    candidate_run_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "candidate-scenario",
            "prompt_version": "candidate-v2",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "scenario": "incident_summary",
                    "slice_name": "database_failover",
                    "severity": "high",
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

    gate_response = client.post(
        "/api/v1/release-gates",
        json={
            "dataset_name": dataset_name,
            "baseline_run_id": baseline_run_response.json()["id"],
            "candidate_run_id": candidate_run_response.json()["id"],
            "min_score_delta": -0.01,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 1,
            "max_scenario_failed_delta": 0,
        },
    )
    assert gate_response.status_code == 201
    payload = gate_response.json()
    assert payload["status"] == "failed"
    assert payload["metrics"]["scenario_failed_delta"] == 1
    assert payload["metrics"]["scenario_metrics"][0]["scenario"] == "incident_summary"
    assert any(failure["metric"] == "scenario_failed_delta" for failure in payload["failures"])
    assert any(failure["code"] == "SCENARIO_FAILED_DELTA_FAIL" for failure in payload["failures"])


def test_release_gate_respects_scenario_and_slice_threshold_overrides() -> None:
    dataset_name = f"release_gate_overrides_{uuid4().hex[:8]}"
    create_dataset_response = client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for release gate threshold override testing.",
            "owner": "test-suite",
        },
    )
    assert create_dataset_response.status_code == 201

    baseline_run_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "baseline-overrides",
            "prompt_version": "baseline-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by a database failover issue.",
                    "scenario": "incident_summary",
                    "slice_name": "database_failover",
                    "severity": "high",
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

    candidate_run_response = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": "candidate-overrides",
            "prompt_version": "candidate-v2",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "scenario": "incident_summary",
                    "slice_name": "database_failover",
                    "severity": "high",
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

    gate_response = client.post(
        "/api/v1/release-gates",
        json={
            "dataset_name": dataset_name,
            "baseline_run_id": baseline_run_response.json()["id"],
            "candidate_run_id": candidate_run_response.json()["id"],
            "min_score_delta": -1.0,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 10,
            "max_scenario_failed_delta": 10,
            "scenario_score_thresholds": {"incident_summary": -0.01},
            "slice_score_thresholds": {"database_failover": -0.01},
            "scenario_failed_case_thresholds": {"incident_summary": 0},
            "slice_failed_case_thresholds": {"database_failover": 0},
        },
    )
    assert gate_response.status_code == 201
    payload = gate_response.json()
    assert payload["status"] == "failed"
    assert payload["metrics"]["slice_metrics"][0]["slice_name"] == "database_failover"
    assert any(
        failure["metric"] == "scenario_score_threshold:incident_summary"
        for failure in payload["failures"]
    )
    assert any(
        failure["metric"] == "slice_score_threshold:database_failover"
        for failure in payload["failures"]
    )


def test_release_gate_summary_endpoint_returns_latest_decision() -> None:
    dataset_name = f"release_gate_summary_{uuid4().hex[:8]}"
    experiment_name = "summary-track"

    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for release summary endpoint testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "baseline-v1",
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
    assert baseline_run.status_code == 201

    candidate_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-v2",
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
    assert candidate_run.status_code == 201

    gate = client.post(
        "/api/v1/release-gates",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "baseline_run_id": baseline_run.json()["id"],
            "candidate_run_id": candidate_run.json()["id"],
            "min_score_delta": -0.5,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 1,
        },
    )
    assert gate.status_code == 201

    summary = client.get(
        "/api/v1/release-gates/summary",
        params={"dataset_name": dataset_name, "experiment_name": experiment_name},
    )
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["dataset_name"] == dataset_name
    assert payload["experiment_name"] == experiment_name
    assert payload["status"] in {"passed", "failed"}
    assert payload["decision_id"] == gate.json()["id"]
    assert isinstance(payload["blocking_failure_codes"], list)


def test_release_gate_policy_endpoint_and_evaluate_latest_policy() -> None:
    policies = client.get("/api/v1/release-gates/policies")
    assert policies.status_code == 200
    policy_payload = policies.json()
    assert any(policy["name"] == "strict" for policy in policy_payload)
    assert any(policy["name"] == "balanced" for policy in policy_payload)
    assert any(policy["name"] == "lenient" for policy in policy_payload)

    dataset_name = f"release_gate_policy_{uuid4().hex[:8]}"
    experiment_name = "policy-track"
    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for policy-preset evaluate-latest testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    older_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "baseline-v1",
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
    assert older_run.status_code == 201

    newer_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-v2",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert newer_run.status_code == 201

    strict_gate = client.post(
        "/api/v1/release-gates/evaluate-latest",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "policy_name": "strict",
        },
    )
    assert strict_gate.status_code == 201
    assert strict_gate.json()["status"] == "failed"
    assert strict_gate.json()["policy_name"] == "strict"

    lenient_gate = client.post(
        "/api/v1/release-gates/evaluate-latest",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "policy_name": "lenient",
        },
    )
    assert lenient_gate.status_code == 201
    assert lenient_gate.json()["status"] == "passed"
    assert lenient_gate.json()["policy_name"] == "lenient"

    report = client.get(
        "/api/v1/release-gates/policy-report",
        params={"dataset_name": dataset_name, "experiment_name": experiment_name, "lookback_days": 30},
    )
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["total_decisions"] >= 2
    policy_names = [item["policy_name"] for item in report_payload["policies"]]
    assert "strict" in policy_names
    assert "lenient" in policy_names


def test_release_gate_ci_decision_endpoint() -> None:
    dataset_name = f"release_gate_ci_{uuid4().hex[:8]}"
    experiment_name = "ci-track"

    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for CI decision endpoint testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "baseline-v1",
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
    assert baseline_run.status_code == 201

    candidate_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-v2",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert candidate_run.status_code == 201

    gate = client.post(
        "/api/v1/release-gates",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "baseline_run_id": baseline_run.json()["id"],
            "candidate_run_id": candidate_run.json()["id"],
            "min_score_delta": -0.01,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 0,
        },
    )
    assert gate.status_code == 201

    ci_decision = client.get(
        "/api/v1/release-gates/ci-decision",
        params={"dataset_name": dataset_name, "experiment_name": experiment_name},
    )
    assert ci_decision.status_code == 200
    payload = ci_decision.json()
    assert payload["dataset_name"] == dataset_name
    assert payload["experiment_name"] == experiment_name
    assert payload["decision_id"] == gate.json()["id"]
    assert payload["allow_deploy"] is False
    assert "SCORE_DELTA_FAIL" in payload["reason_codes"] or "FAILED_CASE_DELTA_FAIL" in payload["reason_codes"]


def test_release_gate_trends_endpoint() -> None:
    dataset_name = f"release_gate_trends_{uuid4().hex[:8]}"
    experiment_name = "trends-track"

    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for release gate trends testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "baseline-v1",
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
    assert baseline_run.status_code == 201

    candidate_pass = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-pass",
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
    assert candidate_pass.status_code == 201

    candidate_fail = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-fail",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert candidate_fail.status_code == 201

    pass_gate = client.post(
        "/api/v1/release-gates",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "baseline_run_id": baseline_run.json()["id"],
            "candidate_run_id": candidate_pass.json()["id"],
            "min_score_delta": -0.5,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 1,
        },
    )
    assert pass_gate.status_code == 201
    assert pass_gate.json()["status"] == "passed"

    fail_gate = client.post(
        "/api/v1/release-gates",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "baseline_run_id": baseline_run.json()["id"],
            "candidate_run_id": candidate_fail.json()["id"],
            "min_score_delta": -0.01,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 0,
        },
    )
    assert fail_gate.status_code == 201
    assert fail_gate.json()["status"] == "failed"

    trends = client.get(
        "/api/v1/release-gates/trends",
        params={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "lookback_days": 30,
        },
    )
    assert trends.status_code == 200
    payload = trends.json()
    assert payload["total_decisions"] == 2
    assert payload["overall_pass_rate"] == 0.5
    assert len(payload["daily"]) >= 1
    assert isinstance(payload["top_failure_codes"], list)


def test_release_gate_evaluate_latest_endpoint() -> None:
    dataset_name = f"release_gate_latest_{uuid4().hex[:8]}"
    experiment_name = "latest-track"

    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for evaluate-latest testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    older_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "baseline-v1",
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
    assert older_run.status_code == 201

    newer_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-v2",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert newer_run.status_code == 201

    gate = client.post(
        "/api/v1/release-gates/evaluate-latest",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "min_score_delta": -0.01,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 0,
        },
    )
    assert gate.status_code == 201
    payload = gate.json()
    assert payload["dataset_name"] == dataset_name
    assert payload["experiment_name"] == experiment_name
    assert payload["baseline_run_id"] == older_run.json()["id"]
    assert payload["candidate_run_id"] == newer_run.json()["id"]


def test_release_gate_evaluate_latest_requires_two_runs() -> None:
    dataset_name = f"release_gate_latest_missing_{uuid4().hex[:8]}"
    experiment_name = "latest-missing"

    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for evaluate-latest missing-runs testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    single_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "only-v1",
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
    assert single_run.status_code == 201

    gate = client.post(
        "/api/v1/release-gates/evaluate-latest",
        json={"dataset_name": dataset_name, "experiment_name": experiment_name},
    )
    assert gate.status_code == 400
    assert "At least two eval runs are required" in gate.json()["detail"]


def test_release_gate_schedule_create_run_and_logs() -> None:
    dataset_name = f"release_gate_schedule_{uuid4().hex[:8]}"
    experiment_name = "schedule-track"

    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for schedule run testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    older_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "baseline-v1",
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
    assert older_run.status_code == 201

    newer_run = client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-v2",
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
    assert newer_run.status_code == 201

    created_schedule = client.post(
        "/api/v1/release-gates/schedules",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "policy_name": "balanced",
            "cron_expression": "0 2 * * *",
            "enabled": True,
        },
    )
    assert created_schedule.status_code == 201
    schedule_id = created_schedule.json()["id"]

    listed_schedules = client.get("/api/v1/release-gates/schedules")
    assert listed_schedules.status_code == 200
    assert any(item["id"] == schedule_id for item in listed_schedules.json())

    run_now = client.post(f"/api/v1/release-gates/schedules/{schedule_id}/run")
    assert run_now.status_code == 201
    run_payload = run_now.json()
    assert run_payload["schedule_id"] == schedule_id
    assert run_payload["status"] in {"completed", "failed"}
    assert run_payload["status"] == "completed"
    assert run_payload["decision_id"] != ""

    logs = client.get(f"/api/v1/release-gates/schedules/{schedule_id}/runs")
    assert logs.status_code == 200
    log_rows = logs.json()
    assert len(log_rows) >= 1
    assert log_rows[0]["schedule_id"] == schedule_id


def test_schedule_run_sends_alert_on_failed_gate(monkeypatch) -> None:
    captured = []

    def _capture_alert(**kwargs) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(release_gate_service, "_send_schedule_alert", _capture_alert)

    dataset_name = f"release_gate_alert_{uuid4().hex[:8]}"
    experiment_name = "schedule-alert-track"

    assert client.post(
        "/api/v1/datasets",
        json={
            "name": dataset_name,
            "description": "Dataset for schedule alert testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    assert client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "baseline-v1",
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
    ).status_code == 201

    assert client.post(
        "/api/v1/evals",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "candidate-v2",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by an infrastructure issue.",
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    ).status_code == 201

    create_schedule = client.post(
        "/api/v1/release-gates/schedules",
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "policy_name": "strict",
            "cron_expression": "0 2 * * *",
            "enabled": True,
        },
    )
    assert create_schedule.status_code == 201
    schedule_id = create_schedule.json()["id"]

    run_now = client.post(f"/api/v1/release-gates/schedules/{schedule_id}/run")
    assert run_now.status_code == 201
    assert run_now.json()["status"] == "completed"
    assert len(captured) == 1
    assert captured[0]["event_type"] == "release_gate_failed"
