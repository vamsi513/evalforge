from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_experiment_registry_tracks_workspace_and_run_count() -> None:
    workspace_headers = {"X-Workspace-ID": "exp-team"}
    dataset_name = f"experiment_dataset_{uuid4().hex[:8]}"
    experiment_name = f"release-readiness-{uuid4().hex[:6]}"

    create_dataset = client.post(
        "/api/v1/datasets",
        headers=workspace_headers,
        json={
            "name": dataset_name,
            "description": "Dataset for experiment registry integration coverage.",
            "owner": "test-suite",
        },
    )
    assert create_dataset.status_code == 201

    create_experiment = client.post(
        "/api/v1/experiments",
        headers=workspace_headers,
        json={
            "name": experiment_name,
            "dataset_name": dataset_name,
            "owner": "test-suite",
            "status": "active",
            "description": "Tracks candidate and baseline runs for release readiness.",
            "experiment_metadata": {"release_track": "canary"},
        },
    )
    assert create_experiment.status_code == 201
    assert create_experiment.json()["workspace_id"] == "exp-team"
    assert create_experiment.json()["run_count"] == 0

    create_run = client.post(
        "/api/v1/evals",
        headers=workspace_headers,
        json={
            "dataset_name": dataset_name,
            "experiment_name": experiment_name,
            "prompt_version": "experiment-v1",
            "model_name": "gpt-4o-mini",
            "samples": [
                {
                    "prompt": "Summarize the outage root cause in one sentence.",
                    "expected_keyword": "database",
                    "candidate_output": "The outage was caused by a database failover issue.",
                    "reference_answer": "The outage was caused by a database failover issue.",
                    "rubric": [],
                }
            ],
        },
    )
    assert create_run.status_code == 201

    list_experiments = client.get("/api/v1/experiments", headers=workspace_headers)
    assert list_experiments.status_code == 200
    experiment = next(item for item in list_experiments.json() if item["name"] == experiment_name)
    assert experiment["dataset_name"] == dataset_name
    assert experiment["workspace_id"] == "exp-team"
    assert experiment["status"] == "active"
    assert experiment["run_count"] == 1


def test_release_gate_links_to_experiment_name() -> None:
    workspace_headers = {"X-Workspace-ID": "exp-gates"}
    dataset_name = f"experiment_gate_dataset_{uuid4().hex[:8]}"
    experiment_name = f"gate-track-{uuid4().hex[:6]}"

    create_dataset = client.post(
        "/api/v1/datasets",
        headers=workspace_headers,
        json={
            "name": dataset_name,
            "description": "Dataset for experiment-linked release gate coverage.",
            "owner": "test-suite",
        },
    )
    assert create_dataset.status_code == 201

    create_experiment = client.post(
        "/api/v1/experiments",
        headers=workspace_headers,
        json={
            "name": experiment_name,
            "dataset_name": dataset_name,
            "owner": "test-suite",
            "status": "active",
            "description": "Tracks release-gate outcomes for the experiment.",
        },
    )
    assert create_experiment.status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        headers=workspace_headers,
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
        headers=workspace_headers,
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

    create_gate = client.post(
        "/api/v1/release-gates",
        headers=workspace_headers,
        json={
            "dataset_name": dataset_name,
            "baseline_run_id": baseline_run.json()["id"],
            "candidate_run_id": candidate_run.json()["id"],
            "min_score_delta": -0.5,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 1,
        },
    )
    assert create_gate.status_code == 201
    assert create_gate.json()["experiment_name"] == experiment_name


def test_experiment_report_includes_runs_and_release_history() -> None:
    workspace_headers = {"X-Workspace-ID": "exp-report"}
    dataset_name = f"experiment_report_dataset_{uuid4().hex[:8]}"
    experiment_name = f"report-track-{uuid4().hex[:6]}"

    assert client.post(
        "/api/v1/datasets",
        headers=workspace_headers,
        json={
            "name": dataset_name,
            "description": "Dataset for experiment report coverage.",
            "owner": "test-suite",
        },
    ).status_code == 201

    assert client.post(
        "/api/v1/experiments",
        headers=workspace_headers,
        json={
            "name": experiment_name,
            "dataset_name": dataset_name,
            "owner": "test-suite",
            "status": "active",
            "description": "Experiment used to validate report history.",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        headers=workspace_headers,
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
        headers=workspace_headers,
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

    assert client.post(
        "/api/v1/release-gates",
        headers=workspace_headers,
        json={
            "dataset_name": dataset_name,
            "baseline_run_id": baseline_run.json()["id"],
            "candidate_run_id": candidate_run.json()["id"],
            "min_score_delta": -0.5,
            "max_latency_regression_ms": 1000,
            "max_cost_regression_usd": 1,
            "max_failed_case_delta": 1,
        },
    ).status_code == 201

    report = client.get(f"/api/v1/experiments/{experiment_name}/report", headers=workspace_headers)
    assert report.status_code == 200
    payload = report.json()
    assert payload["experiment"]["name"] == experiment_name
    assert len(payload["recent_runs"]) == 2
    assert len(payload["release_gates"]) == 1
    assert payload["latest_gate_status"] in {"passed", "failed"}
    assert len(payload["score_trend"]) == 2


def test_promote_candidate_succeeds_when_latest_gate_passed() -> None:
    workspace_headers = {"X-Workspace-ID": "exp-promote-pass"}
    dataset_name = f"experiment_promote_dataset_{uuid4().hex[:8]}"
    experiment_name = f"promote-pass-{uuid4().hex[:6]}"

    assert client.post(
        "/api/v1/datasets",
        headers=workspace_headers,
        json={
            "name": dataset_name,
            "description": "Dataset for candidate promotion success test.",
            "owner": "test-suite",
        },
    ).status_code == 201

    assert client.post(
        "/api/v1/experiments",
        headers=workspace_headers,
        json={
            "name": experiment_name,
            "dataset_name": dataset_name,
            "owner": "test-suite",
            "status": "active",
            "description": "Experiment used to validate promotion flow.",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        headers=workspace_headers,
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
        headers=workspace_headers,
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

    assert client.post(
        "/api/v1/release-gates",
        headers=workspace_headers,
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
    ).status_code == 201

    promote = client.post(
        f"/api/v1/experiments/{experiment_name}/promote",
        headers=workspace_headers,
        json={"candidate_run_id": "", "require_latest_gate_passed": True},
    )
    assert promote.status_code == 200
    payload = promote.json()
    assert payload["gate_status"] == "passed"
    assert payload["promoted_run_id"] == candidate_run.json()["id"]
    assert payload["updated_experiment"]["baseline_run_id"] == candidate_run.json()["id"]
    assert payload["updated_experiment"]["status"] == "baseline"


def test_promote_candidate_blocked_when_latest_gate_failed() -> None:
    workspace_headers = {"X-Workspace-ID": "exp-promote-fail"}
    dataset_name = f"experiment_promote_fail_dataset_{uuid4().hex[:8]}"
    experiment_name = f"promote-fail-{uuid4().hex[:6]}"

    assert client.post(
        "/api/v1/datasets",
        headers=workspace_headers,
        json={
            "name": dataset_name,
            "description": "Dataset for candidate promotion failure test.",
            "owner": "test-suite",
        },
    ).status_code == 201

    assert client.post(
        "/api/v1/experiments",
        headers=workspace_headers,
        json={
            "name": experiment_name,
            "dataset_name": dataset_name,
            "owner": "test-suite",
            "status": "active",
            "description": "Experiment used to validate failed-gate promotion blocking.",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        headers=workspace_headers,
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
        headers=workspace_headers,
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
        headers=workspace_headers,
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
    assert gate.json()["status"] == "failed"

    promote = client.post(
        f"/api/v1/experiments/{experiment_name}/promote",
        headers=workspace_headers,
        json={"candidate_run_id": "", "require_latest_gate_passed": True},
    )
    assert promote.status_code == 400
    assert "Latest release gate did not pass" in promote.json()["detail"]


def test_release_history_includes_promotion_events() -> None:
    workspace_headers = {"X-Workspace-ID": "exp-history"}
    dataset_name = f"experiment_history_dataset_{uuid4().hex[:8]}"
    experiment_name = f"history-track-{uuid4().hex[:6]}"

    assert client.post(
        "/api/v1/datasets",
        headers=workspace_headers,
        json={
            "name": dataset_name,
            "description": "Dataset for promotion history endpoint testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    assert client.post(
        "/api/v1/experiments",
        headers=workspace_headers,
        json={
            "name": experiment_name,
            "dataset_name": dataset_name,
            "owner": "test-suite",
            "status": "active",
            "description": "Experiment for immutable promotion event history.",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        headers=workspace_headers,
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
        headers=workspace_headers,
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
        headers=workspace_headers,
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

    promote = client.post(
        f"/api/v1/experiments/{experiment_name}/promote",
        headers=workspace_headers,
        json={"candidate_run_id": "", "require_latest_gate_passed": True},
    )
    assert promote.status_code == 200

    history = client.get(
        f"/api/v1/experiments/{experiment_name}/release-history",
        headers=workspace_headers,
    )
    assert history.status_code == 200
    events = history.json()
    assert len(events) >= 1
    assert events[0]["experiment_name"] == experiment_name
    assert events[0]["gate_id"] == gate.json()["id"]
    assert events[0]["promoted_run_id"] == candidate_run.json()["id"]


def test_release_history_csv_export() -> None:
    workspace_headers = {"X-Workspace-ID": "exp-history-csv"}
    dataset_name = f"experiment_history_csv_dataset_{uuid4().hex[:8]}"
    experiment_name = f"history-csv-{uuid4().hex[:6]}"

    assert client.post(
        "/api/v1/datasets",
        headers=workspace_headers,
        json={
            "name": dataset_name,
            "description": "Dataset for promotion history csv export testing.",
            "owner": "test-suite",
        },
    ).status_code == 201

    assert client.post(
        "/api/v1/experiments",
        headers=workspace_headers,
        json={
            "name": experiment_name,
            "dataset_name": dataset_name,
            "owner": "test-suite",
            "status": "active",
            "description": "Experiment for csv export history coverage.",
        },
    ).status_code == 201

    baseline_run = client.post(
        "/api/v1/evals",
        headers=workspace_headers,
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
        headers=workspace_headers,
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
        headers=workspace_headers,
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

    promote = client.post(
        f"/api/v1/experiments/{experiment_name}/promote",
        headers=workspace_headers,
        json={"candidate_run_id": "", "require_latest_gate_passed": True},
    )
    assert promote.status_code == 200

    history_csv = client.get(
        f"/api/v1/experiments/{experiment_name}/release-history/export.csv",
        headers=workspace_headers,
    )
    assert history_csv.status_code == 200
    assert history_csv.headers["content-type"].startswith("text/csv")
    assert "attachment;" in history_csv.headers.get("content-disposition", "")
    body = history_csv.text
    assert "experiment_name,dataset_name,gate_id" in body
    assert experiment_name in body
    assert gate.json()["id"] in body
