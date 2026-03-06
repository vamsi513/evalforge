import pandas as pd
import streamlit as st
from httpx import HTTPError

from client import EvalForgeClient


st.set_page_config(page_title="EvalForge", page_icon="EF", layout="wide")

st.title("EvalForge Dashboard")
st.caption("Reliability, PromptOps, and evaluation telemetry for LLM systems.")

base_url = st.sidebar.text_input("API Base URL", value="http://127.0.0.1:8001")
api_key = st.sidebar.text_input("API Key", value="", type="password")
workspace_id = st.sidebar.text_input("Workspace", value="default")
refresh = st.sidebar.button("Refresh")

@st.cache_data(show_spinner=False)
def load_snapshot(api_base_url: str, api_key_value: str, workspace: str) -> dict:
    api = EvalForgeClient(api_base_url, api_key=api_key_value, workspace_id=workspace)
    return {
        "health": api.get_health(),
        "telemetry": api.get_telemetry(),
        "datasets": api.get_datasets(),
        "evaluators": api.get_evaluators(),
        "experiments": api.get_experiments(),
        "prompts": api.get_prompt_templates(),
        "golden_cases": api.get_golden_cases(),
        "runs": api.get_runs(),
        "jobs": api.get_jobs(),
        "release_gates": api.get_release_gates(),
        "release_gate_policies": api.get_release_gate_policies(),
        "release_gate_trends": api.get_release_gate_trends(lookback_days=30),
        "model_routes": api.get_model_routes(),
    }


if refresh:
    load_snapshot.clear()

try:
    snapshot = load_snapshot(base_url, api_key, workspace_id)
except HTTPError as exc:
    st.error(f"Failed to load API data from {base_url}: {exc}")
    st.stop()

health = snapshot["health"]
telemetry = snapshot["telemetry"]
datasets = snapshot["datasets"]
evaluators = snapshot["evaluators"]
experiments = snapshot["experiments"]
prompts = snapshot["prompts"]
golden_cases = snapshot["golden_cases"]
runs = snapshot["runs"]
jobs = snapshot["jobs"]
release_gates = snapshot["release_gates"]
release_gate_policies = snapshot["release_gate_policies"]
release_gate_trends = snapshot["release_gate_trends"]
model_routes = snapshot["model_routes"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Service", health.get("service", "unknown"))
col2.metric("Workspace", workspace_id or "default")
col3.metric("Total Runs", telemetry.get("total_runs", 0))
col4.metric("Average Score", telemetry.get("average_score", 0.0))

col_env, _, _, _ = st.columns(4)
col_env.metric("Environment", health.get("environment", "unknown"))

col5, col6 = st.columns(2)
col5.metric("Total Cost (USD)", telemetry.get("total_cost_usd", 0.0))
col6.metric("Avg Latency (ms)", telemetry.get("average_latency_ms", 0.0))

job_status_counts = {
    "queued": sum(1 for job in jobs if job["status"] == "queued"),
    "running": sum(1 for job in jobs if job["status"] == "running"),
    "completed": sum(1 for job in jobs if job["status"] == "completed"),
    "failed": sum(1 for job in jobs if job["status"] == "failed"),
}

col7, col8, col9, col10 = st.columns(4)
col7.metric("Queued Jobs", job_status_counts["queued"])
col8.metric("Running Jobs", job_status_counts["running"])
col9.metric("Completed Jobs", job_status_counts["completed"])
col10.metric("Failed Jobs", job_status_counts["failed"])

gate_status_counts = {
    "passed": sum(1 for gate in release_gates if gate["status"] == "passed"),
    "failed": sum(1 for gate in release_gates if gate["status"] == "failed"),
}

col11, col12 = st.columns(2)
col11.metric("Passed Gates", gate_status_counts["passed"])
col12.metric("Failed Gates", gate_status_counts["failed"])

col_exp, _, _, _ = st.columns(4)
col_exp.metric("Experiments", len(experiments))

col_eval, _, _, _ = st.columns(4)
col_eval.metric("Evaluators", len(evaluators))
col_routes, _, _, _ = st.columns(4)
col_routes.metric("Routing Policies", len(model_routes))

col13, col14 = st.columns(2)
col13.metric("Structured Output Pass Rate", telemetry.get("structured_output_pass_rate", 1.0))
col14.metric("Structured Output Failures", telemetry.get("structured_output_failure_count", 0))

col15, col16 = st.columns(2)
col15.metric("Groundedness Avg", telemetry.get("groundedness_average", 1.0))
col16.metric("Groundedness Failures", telemetry.get("groundedness_failure_count", 0))

exp_rollups = telemetry.get("experiment_rollups", [])
use_case_rollups = telemetry.get("use_case_rollups", [])
if exp_rollups or use_case_rollups:
    st.markdown("### Telemetry Rollups")
    rollup_col1, rollup_col2 = st.columns(2)
    with rollup_col1:
        st.markdown("**By Experiment**")
        if exp_rollups:
            st.dataframe(pd.DataFrame(exp_rollups), use_container_width=True)
        else:
            st.info("No experiment rollups yet.")
    with rollup_col2:
        st.markdown("**By Use Case**")
        if use_case_rollups:
            st.dataframe(pd.DataFrame(use_case_rollups), use_container_width=True)
        else:
            st.info("No use-case rollups yet.")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(
    [
        "Runs",
        "Jobs",
        "Release Gates",
        "Experiments",
        "Evaluators",
        "Model Routing",
        "Datasets",
        "Golden Cases",
        "Prompt Templates",
    ]
)

with tab1:
    st.subheader("Recent Eval Runs")
    if not runs:
        st.info("No eval runs found yet.")
    else:
        run_rows = [
            {
                "run_id": run["id"],
                "workspace": run.get("workspace_id", "default"),
                "dataset": run["dataset_name"],
                "prompt_version": run["prompt_version"],
                "model": run["model_name"],
                "average_score": run["average_score"],
                "structured_failures": sum(
                    1 for result in run["results"] if result.get("required_json_fields") and not result.get("structured_output_valid")
                ),
                "created_at": run["created_at"],
                "cases": len(run["results"]),
            }
            for run in runs
        ]
        st.dataframe(pd.DataFrame(run_rows), use_container_width=True)

        selected_run_id = st.selectbox("Inspect run", [run["id"] for run in runs])
        selected_run = next(run for run in runs if run["id"] == selected_run_id)
        st.json(selected_run)

with tab2:
    st.subheader("Async Eval Jobs")
    if not jobs:
        st.info("No async jobs found yet.")
    else:
        job_rows = [
            {
                "job_id": job["id"],
                "type": job["job_type"],
                "status": job["status"],
                "workspace": job.get("workspace_id", "default"),
                "dataset": job["dataset_name"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
                "has_result": bool(job.get("result")),
                "error_message": job.get("error_message", ""),
            }
            for job in jobs
        ]
        st.dataframe(pd.DataFrame(job_rows), use_container_width=True)

        selected_job_id = st.selectbox("Inspect job", [job["id"] for job in jobs])
        selected_job = next(job for job in jobs if job["id"] == selected_job_id)
        st.json(selected_job)

with tab3:
    st.subheader("Release Gate Decisions")
    st.markdown("### Evaluate Latest Runs")
    dataset_options = [dataset.get("name", "") for dataset in datasets if dataset.get("name")]
    default_dataset = dataset_options[0] if dataset_options else ""
    with st.form("evaluate_latest_gate_form", clear_on_submit=False):
        selected_dataset = st.selectbox(
            "Dataset",
            options=dataset_options if dataset_options else [""],
            index=0,
        )
        experiment_name = st.text_input("Experiment (optional)", value="")
        policy_options = ["custom"] + [policy.get("name", "") for policy in release_gate_policies]
        selected_policy = st.selectbox("Policy preset", options=policy_options, index=1 if len(policy_options) > 1 else 0)
        if selected_policy != "custom":
            policy_details = next(
                (policy for policy in release_gate_policies if policy.get("name") == selected_policy),
                None,
            )
            if policy_details:
                st.caption(policy_details.get("description", ""))
                st.json(policy_details)
        threshold_col1, threshold_col2, threshold_col3, threshold_col4 = st.columns(4)
        min_score_delta = threshold_col1.number_input(
            "Min score delta", value=-0.02, min_value=-1.0, max_value=1.0, step=0.01
        )
        max_latency_regression_ms = threshold_col2.number_input(
            "Max latency regression (ms)", value=25.0, min_value=0.0, step=1.0
        )
        max_cost_regression_usd = threshold_col3.number_input(
            "Max cost regression (USD)", value=0.001, min_value=0.0, step=0.001, format="%.6f"
        )
        max_failed_case_delta = int(
            threshold_col4.number_input("Max failed-case delta", value=0, min_value=0, step=1)
        )
        submit_evaluate_latest = st.form_submit_button("Run Evaluate-Latest Gate")

    if submit_evaluate_latest:
        if not selected_dataset and not default_dataset:
            st.error("Create at least one dataset before running evaluate-latest gate.")
        else:
            evaluate_api = EvalForgeClient(base_url, api_key=api_key, workspace_id=workspace_id)
            try:
                created_gate = evaluate_api.evaluate_latest_release_gate(
                    {
                        "dataset_name": selected_dataset or default_dataset,
                        "experiment_name": experiment_name.strip(),
                        "policy_name": "" if selected_policy == "custom" else selected_policy,
                        "min_score_delta": min_score_delta,
                        "max_latency_regression_ms": max_latency_regression_ms,
                        "max_cost_regression_usd": max_cost_regression_usd,
                        "max_failed_case_delta": max_failed_case_delta,
                    }
                )
                st.success("Release gate created from latest runs.")
                st.json(created_gate)
                load_snapshot.clear()
            except HTTPError as exc:
                st.error(f"Failed to run evaluate-latest gate: {exc}")

    trend_col1, trend_col2 = st.columns(2)
    with trend_col1:
        st.metric("Gate Decisions (30d)", release_gate_trends.get("total_decisions", 0))
        st.metric("Gate Pass Rate (30d)", release_gate_trends.get("overall_pass_rate", 0.0))
    with trend_col2:
        top_codes = release_gate_trends.get("top_failure_codes", [])
        if top_codes:
            st.markdown("**Top Failure Codes (30d)**")
            st.dataframe(pd.DataFrame(top_codes), use_container_width=True)
        else:
            st.info("No blocking failure codes in the lookback window.")

    daily_trends = release_gate_trends.get("daily", [])
    if daily_trends:
        trend_df = pd.DataFrame(daily_trends).set_index("date")
        st.markdown("**Daily Gate Pass Rate (30d)**")
        st.line_chart(trend_df[["pass_rate"]], use_container_width=True)

    if not release_gates:
        st.info("No release gate decisions found.")
    else:
        gate_rows = [
            {
                "gate_id": gate["id"],
                "workspace": gate.get("workspace_id", "default"),
                "experiment": gate.get("experiment_name", ""),
                "dataset": gate["dataset_name"],
                "status": gate["status"],
                "score_delta": gate["metrics"].get("score_delta", 0.0),
                "failed_case_delta": gate["metrics"].get("failed_case_delta", 0),
                "scenario_failed_delta": gate["metrics"].get("scenario_failed_delta", 0),
                "created_at": gate["created_at"],
            }
            for gate in release_gates
        ]
        st.dataframe(pd.DataFrame(gate_rows), use_container_width=True)

        selected_gate_id = st.selectbox("Inspect release gate", [gate["id"] for gate in release_gates])
        selected_gate = next(gate for gate in release_gates if gate["id"] == selected_gate_id)
        st.json(selected_gate)

        scenario_metrics = selected_gate.get("metrics", {}).get("scenario_metrics", [])
        if scenario_metrics:
            st.markdown("**Scenario Regressions**")
            st.dataframe(pd.DataFrame(scenario_metrics), use_container_width=True)
        slice_metrics = selected_gate.get("metrics", {}).get("slice_metrics", [])
        if slice_metrics:
            st.markdown("**Slice Regressions**")
            st.dataframe(pd.DataFrame(slice_metrics), use_container_width=True)

with tab4:
    st.subheader("Experiment Registry")
    if not experiments:
        st.info("No experiments found.")
    else:
        experiment_rows = [
            {
                "id": experiment["id"],
                "workspace": experiment.get("workspace_id", "default"),
                "name": experiment["name"],
                "dataset": experiment["dataset_name"],
                "owner": experiment["owner"],
                "status": experiment["status"],
                "run_count": experiment.get("run_count", 0),
                "baseline_run_id": experiment.get("baseline_run_id", ""),
                "candidate_run_id": experiment.get("candidate_run_id", ""),
                "updated_at": experiment["updated_at"],
            }
            for experiment in experiments
        ]
        st.dataframe(pd.DataFrame(experiment_rows), use_container_width=True)

        selected_experiment_id = st.selectbox("Inspect experiment", [experiment["id"] for experiment in experiments])
        selected_experiment = next(experiment for experiment in experiments if experiment["id"] == selected_experiment_id)
        st.json(selected_experiment)

        st.markdown("**Release Promotion**")
        promote_candidate_run_id = st.text_input(
            "Candidate run id override (optional)",
            value="",
            key=f"promote_candidate_override_{selected_experiment_id}",
            help="Leave empty to promote the candidate run from the latest release-gate decision.",
        )
        promote_btn = st.button(
            "Promote Candidate to Baseline",
            key=f"promote_candidate_btn_{selected_experiment_id}",
        )
        if promote_btn:
            experiment_api = EvalForgeClient(base_url, api_key=api_key, workspace_id=workspace_id)
            try:
                promotion = experiment_api.promote_experiment_candidate(
                    selected_experiment["name"],
                    candidate_run_id=promote_candidate_run_id.strip(),
                    require_latest_gate_passed=True,
                )
                st.success("Promotion completed.")
                st.json(promotion)
                load_snapshot.clear()
            except HTTPError as exc:
                st.error(f"Promotion failed: {exc}")

        experiment_api = EvalForgeClient(base_url, api_key=api_key, workspace_id=workspace_id)
        experiment_report = experiment_api.get_experiment_report(selected_experiment["name"])
        release_history_events = experiment_api.get_experiment_release_history(selected_experiment["name"])

        recent_runs = experiment_report.get("recent_runs", [])
        if recent_runs:
            st.markdown("**Recent Runs**")
            st.dataframe(pd.DataFrame(recent_runs), use_container_width=True)

        release_history = experiment_report.get("release_gates", [])
        if release_history:
            st.markdown("**Release History**")
            st.dataframe(pd.DataFrame(release_history), use_container_width=True)

        if release_history_events:
            st.markdown("**Promotion Audit Log**")
            st.dataframe(pd.DataFrame(release_history_events), use_container_width=True)
            try:
                csv_payload = experiment_api.get_experiment_release_history_csv(selected_experiment["name"])
                st.download_button(
                    label="Download Promotion Audit CSV",
                    data=csv_payload,
                    file_name=f"{selected_experiment['name']}_release_history.csv",
                    mime="text/csv",
                    key=f"download_release_history_{selected_experiment_id}",
                )
            except HTTPError as exc:
                st.warning(f"Could not generate release history CSV: {exc}")

        score_trend = experiment_report.get("score_trend", [])
        if score_trend:
            st.markdown("**Score Trend**")
            st.line_chart(pd.DataFrame({"average_score": list(reversed(score_trend))}))

with tab5:
    st.subheader("Evaluator Registry")
    if not evaluators:
        st.info("No evaluator definitions found.")
    else:
        evaluator_rows = [
            {
                "id": evaluator["id"],
                "name": evaluator["name"],
                "version": evaluator["version"],
                "kind": evaluator["kind"],
                "status": evaluator["status"],
                "updated_at": evaluator["updated_at"],
            }
            for evaluator in evaluators
        ]
        st.dataframe(pd.DataFrame(evaluator_rows), use_container_width=True)

        selected_evaluator_id = st.selectbox("Inspect evaluator", [evaluator["id"] for evaluator in evaluators])
        selected_evaluator = next(evaluator for evaluator in evaluators if evaluator["id"] == selected_evaluator_id)
        st.json(selected_evaluator)

with tab6:
    st.subheader("Model Routing Registry")
    if not model_routes:
        st.info("No routing policies found.")
    else:
        route_rows = [
            {
                "id": route["id"],
                "workspace": route.get("workspace_id", "default"),
                "use_case": route["use_case"],
                "version": route["version"],
                "primary": f"{route['primary_provider']} / {route['primary_model']}",
                "fallback": f"{route.get('fallback_provider', '')} / {route.get('fallback_model', '')}".strip(" /"),
                "status": route["status"],
                "updated_at": route["updated_at"],
            }
            for route in model_routes
        ]
        st.dataframe(pd.DataFrame(route_rows), use_container_width=True)

        selected_route_id = st.selectbox("Inspect model route", [route["id"] for route in model_routes])
        selected_route = next(route for route in model_routes if route["id"] == selected_route_id)
        st.json(selected_route)

with tab7:
    st.subheader("Datasets")
    if not datasets:
        st.info("No datasets found.")
    else:
        st.dataframe(pd.DataFrame(datasets), use_container_width=True)

with tab8:
    st.subheader("Golden Cases")
    if not golden_cases:
        st.info("No golden cases found.")
    else:
        case_rows = [
            {
                "id": case["id"],
                "dataset": case["dataset_name"],
                "scenario": case.get("scenario", "general"),
                "slice_name": case.get("slice_name", "default"),
                "severity": case.get("severity", "medium"),
                "expected_keyword": case["expected_keyword"],
                "tags": ", ".join(case.get("tags", [])),
                "created_at": case["created_at"],
            }
            for case in golden_cases
        ]
        st.dataframe(pd.DataFrame(case_rows), use_container_width=True)

        selected_case_id = st.selectbox("Inspect golden case", [case["id"] for case in golden_cases])
        selected_case = next(case for case in golden_cases if case["id"] == selected_case_id)
        st.json(selected_case)

with tab9:
    st.subheader("Prompt Templates")
    if not prompts:
        st.info("No prompt templates found.")
    else:
        prompt_rows = [
            {
                "id": prompt["id"],
                "dataset": prompt["dataset_name"],
                "version": prompt["version"],
                "created_at": prompt["created_at"],
            }
            for prompt in prompts
        ]
        st.dataframe(pd.DataFrame(prompt_rows), use_container_width=True)

        selected_prompt_id = st.selectbox("Inspect prompt template", [prompt["id"] for prompt in prompts])
        selected_prompt = next(prompt for prompt in prompts if prompt["id"] == selected_prompt_id)
        st.json(selected_prompt)
