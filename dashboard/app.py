import pandas as pd
import streamlit as st
from client import EvalForgeClient
from httpx import HTTPError

st.set_page_config(
    page_title="EvalForge",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    base_url = st.text_input(
        "API URL",
        value="http://23.21.42.197:8001",
        help="Address of the EvalForge API server",
    )
    api_key = st.text_input("API Key (optional)", value="", type="password")
    workspace_id = st.text_input("Workspace", value="default")
    st.button("🔄 Refresh")

    st.markdown("---")
    st.markdown(
        """
**What is EvalForge?**

EvalForge automatically tests your AI system to make sure it stays accurate, fast, and reliable — before any update goes live.

Think of it as a quality-control department for AI.
        """
    )


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=30)
def load_data(api_base_url: str, api_key_value: str, workspace: str) -> dict:
    api = EvalForgeClient(api_base_url, api_key=api_key_value, workspace_id=workspace)
    return {
        "health": api.get_health(),
        "telemetry": api.get_telemetry(),
        "runs": api.get_runs(),
        "experiments": api.get_experiments(),
        "release_gates": api.get_release_gates(),
        "datasets": api.get_datasets(),
        "release_gate_trends": api.get_release_gate_trends(lookback_days=30),
        "experiment_leaderboard": api.get_experiment_leaderboard(lookback_runs=20, limit=10),
    }


try:
    with st.spinner("Loading data…"):
        data = load_data(base_url, api_key, workspace_id)
except HTTPError as exc:
    st.error(
        f"**Cannot reach the API.** Check that the server is running and the URL is correct.\n\n"
        f"Error: `{exc}`"
    )
    st.stop()


health = data["health"]
telemetry = data["telemetry"]
runs = data["runs"]
experiments = data["experiments"]
release_gates = data["release_gates"]
datasets = data["datasets"]
gate_trends = data["release_gate_trends"]
leaderboard = data["experiment_leaderboard"].get("items", [])

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 🔬 EvalForge")
st.markdown("**Automatic quality control for AI systems** — track accuracy, catch regressions, block bad deploys.")

is_healthy = health.get("status", "") == "ok"
status_badge = "🟢 **System Online**" if is_healthy else "🔴 **System Offline**"
st.markdown(status_badge)
st.divider()

# ── Top-level numbers ──────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

avg_score = telemetry.get("average_score", 0.0)
total_runs = telemetry.get("total_runs", 0)
total_cost = telemetry.get("total_cost_usd", 0.0)
avg_latency = telemetry.get("average_latency_ms", 0.0)

score_color = "🟢" if avg_score >= 0.75 else ("🟡" if avg_score >= 0.5 else "🔴")
col1.metric(f"{score_color} Average Quality Score", f"{avg_score:.0%}", help="How well the AI answers test questions on average. Higher is better.")
col2.metric("🧪 Total Tests Run", f"{total_runs:,}", help="Number of individual AI responses evaluated.")
col3.metric("⚡ Avg Response Time", f"{avg_latency:.0f} ms", help="How fast the AI responds on average.")
col4.metric("💰 Compute Cost", f"${total_cost:.4f}", help="Total OpenAI API cost for all evaluations.")

st.divider()

# ── Release gate summary ───────────────────────────────────────────────────────
st.markdown("## 🚦 Deployment Safety")
st.markdown(
    "Release gates automatically check whether an AI update is safe to deploy. "
    "A **PASSED** gate means the new version is better (or no worse) than the current one."
)

passed = sum(1 for g in release_gates if g.get("status") == "passed")
failed = sum(1 for g in release_gates if g.get("status") == "failed")
total_gates = passed + failed

gcol1, gcol2, gcol3 = st.columns(3)
gcol1.metric("✅ Gates Passed", passed)
gcol2.metric("❌ Gates Failed", failed)
gcol3.metric(
    "Pass Rate (30 days)",
    f"{gate_trends.get('overall_pass_rate', 0.0):.0%}" if total_gates else "—",
)

daily = gate_trends.get("daily", [])
if daily:
    trend_df = pd.DataFrame(daily).set_index("date")
    st.markdown("**Daily pass rate — last 30 days**")
    st.area_chart(trend_df[["pass_rate"]], use_container_width=True, height=160)

# Recent gates
if release_gates:
    st.markdown("**Recent deployment checks**")
    gate_rows = []
    for g in release_gates[:10]:
        status = g.get("status", "unknown")
        icon = "✅" if status == "passed" else "❌"
        gate_rows.append({
            "Result": f"{icon} {status.upper()}",
            "Dataset": g.get("dataset_name", "—"),
            "Experiment": g.get("experiment_name", "—"),
            "Score Change": f"{g['metrics'].get('score_delta', 0):+.3f}" if g.get("metrics") else "—",
            "Date": g.get("created_at", "")[:10],
        })
    st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)

st.divider()

# ── Experiment comparison ──────────────────────────────────────────────────────
st.markdown("## 🧬 Experiment Leaderboard")
st.markdown(
    "Experiments compare different AI configurations (e.g. different prompts or models). "
    "The leaderboard ranks them by quality score."
)

if leaderboard:
    lb_rows = []
    for i, item in enumerate(leaderboard):
        lb_rows.append({
            "Rank": f"#{i+1}",
            "Experiment": item.get("experiment_name", "—"),
            "Model": item.get("model_name", "—"),
            "Quality Score": f"{item.get('average_score', 0):.0%}",
            "Tests Run": item.get("run_count", 0),
            "Avg Latency": f"{item.get('average_latency_ms', 0):.0f} ms",
        })
    st.dataframe(pd.DataFrame(lb_rows), use_container_width=True, hide_index=True)
else:
    st.info("No experiments run yet. Start by creating a dataset and running an evaluation.")

st.divider()

# ── Recent test runs ───────────────────────────────────────────────────────────
st.markdown("## 📋 Recent Test Results")
st.markdown(
    "Each row is one batch of tests — a specific AI prompt tested against a dataset. "
    "The score shows what percentage of answers met the quality bar."
)

if runs:
    run_rows = []
    for run in runs[:15]:
        score = run.get("average_score", 0.0)
        icon = "🟢" if score >= 0.75 else ("🟡" if score >= 0.5 else "🔴")
        run_rows.append({
            "Score": f"{icon} {score:.0%}",
            "Dataset": run.get("dataset_name", "—"),
            "Model": run.get("model_name", "—"),
            "Prompt Version": run.get("prompt_version", "—"),
            "Cases Tested": len(run.get("results", [])),
            "Date": run.get("created_at", "")[:10],
        })
    st.dataframe(pd.DataFrame(run_rows), use_container_width=True, hide_index=True)

    # Score distribution bar chart
    scores = [r.get("average_score", 0.0) for r in runs]
    if scores:
        st.markdown("**Quality score per run (most recent first)**")
        st.bar_chart(
            pd.DataFrame({"Score": scores[:20][::-1]}),
            use_container_width=True,
            height=200,
        )
else:
    st.info("No test runs yet.")

st.divider()

# ── Datasets ───────────────────────────────────────────────────────────────────
st.markdown("## 📂 Test Datasets")
st.markdown(
    "A dataset is a collection of question-and-answer pairs used to test the AI. "
    "More test cases = more confidence in the results."
)

if datasets:
    ds_rows = [
        {
            "Dataset Name": d.get("name", "—"),
            "Cases": d.get("case_count", "—"),
            "Created": d.get("created_at", "")[:10],
        }
        for d in datasets
    ]
    st.dataframe(pd.DataFrame(ds_rows), use_container_width=True, hide_index=True)
else:
    st.info("No datasets yet.")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"EvalForge · workspace: **{workspace_id}** · "
    f"environment: **{health.get('environment', 'unknown')}** · "
    "Built by [Vamsi Krishna Sadu](https://github.com/vamsi513)"
)
