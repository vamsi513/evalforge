import pandas as pd
import streamlit as st
from httpx import HTTPError

from client import EvalForgeClient


st.set_page_config(page_title="EvalForge", page_icon="EF", layout="wide")

st.title("EvalForge Dashboard")
st.caption("Reliability, PromptOps, and evaluation telemetry for LLM systems.")

base_url = st.sidebar.text_input("API Base URL", value="http://127.0.0.1:8000")
refresh = st.sidebar.button("Refresh")

client = EvalForgeClient(base_url)


@st.cache_data(show_spinner=False)
def load_snapshot(api_base_url: str) -> dict:
    api = EvalForgeClient(api_base_url)
    return {
        "health": api.get_health(),
        "telemetry": api.get_telemetry(),
        "datasets": api.get_datasets(),
        "prompts": api.get_prompt_templates(),
        "golden_cases": api.get_golden_cases(),
        "runs": api.get_runs(),
        "jobs": api.get_jobs(),
    }


if refresh:
    load_snapshot.clear()

try:
    snapshot = load_snapshot(base_url)
except HTTPError as exc:
    st.error(f"Failed to load API data from {base_url}: {exc}")
    st.stop()

health = snapshot["health"]
telemetry = snapshot["telemetry"]
datasets = snapshot["datasets"]
prompts = snapshot["prompts"]
golden_cases = snapshot["golden_cases"]
runs = snapshot["runs"]
jobs = snapshot["jobs"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Service", health.get("service", "unknown"))
col2.metric("Environment", health.get("environment", "unknown"))
col3.metric("Total Runs", telemetry.get("total_runs", 0))
col4.metric("Average Score", telemetry.get("average_score", 0.0))

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

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Runs", "Jobs", "Datasets", "Golden Cases", "Prompt Templates"]
)

with tab1:
    st.subheader("Recent Eval Runs")
    if not runs:
        st.info("No eval runs found yet.")
    else:
        run_rows = [
            {
                "run_id": run["id"],
                "dataset": run["dataset_name"],
                "prompt_version": run["prompt_version"],
                "model": run["model_name"],
                "average_score": run["average_score"],
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
    st.subheader("Datasets")
    if not datasets:
        st.info("No datasets found.")
    else:
        st.dataframe(pd.DataFrame(datasets), use_container_width=True)

with tab4:
    st.subheader("Golden Cases")
    if not golden_cases:
        st.info("No golden cases found.")
    else:
        case_rows = [
            {
                "id": case["id"],
                "dataset": case["dataset_name"],
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

with tab5:
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
