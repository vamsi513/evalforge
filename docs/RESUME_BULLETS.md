# EvalForge Resume Bullets

- Built `EvalForge`, an end-to-end LLM Reliability and PromptOps platform with FastAPI, SQLAlchemy, Streamlit, and persistent evaluation telemetry across 8+ API workflows.
- Designed reusable golden-dataset and prompt-template management flows, including dataset bundle import/export for portable regression testing across environments.
- Implemented synchronous, judge-based, pairwise, and async evaluation pipelines to score outputs, compare prompt versions, and monitor job completion state.
- Added OpenAI-compatible structured judging with JSON-schema constrained parsing and safe fallback to deterministic heuristic scoring.
- Engineered persisted async job execution and polling APIs to support background evaluation workloads and dashboard-based observability.
- Built a Streamlit dashboard surfacing run metrics, latency, cost, dataset assets, and async job status for fast operational inspection.
- Introduced Alembic-based schema migration support and Postgres-ready configuration while preserving a lightweight SQLite local-development path.
- Structured the project as a production-style AI system with separable API, service, engine, storage, and dashboard layers instead of a notebook-based prototype.
