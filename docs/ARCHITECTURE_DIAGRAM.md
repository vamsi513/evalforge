# EvalForge Architecture Diagram

## System Diagram

```mermaid
flowchart LR
    UI["Swagger + Streamlit Dashboard"] --> API["FastAPI API Layer"]
    API --> AUTH["Auth + Workspace Scoping"]
    API --> ASSETS["Dataset/Prompt/Golden Asset Services"]
    API --> EVAL["Evaluation Service"]
    API --> GATE["Release Gate Service"]
    API --> EXP["Experiment Service"]
    API --> TEL["Telemetry Service"]
    API --> JOBS["Async Job Service"]

    EVAL --> JUDGE["Judge Engine (Mock/OpenAI-Compatible)"]
    EVAL --> SCORE["Heuristic + Structured Scoring"]
    GATE --> SCORE
    EXP --> GATE

    JOBS --> WORKER["Local Worker / Redis Worker"]
    WORKER --> EVAL

    ASSETS --> DB[(Postgres/SQLite)]
    EVAL --> DB
    GATE --> DB
    EXP --> DB
    TEL --> DB
    JOBS --> DB

    CI["GitHub Actions"] --> DECISION["/release-gates/ci-decision"]
    DECISION --> API
```

## Key Design Decisions

- Service-oriented backend modules isolate asset management, evaluation, telemetry, and release policy logic.
- Evaluation supports sync and async entry points so teams can run interactive checks and batch regressions.
- Judge scoring is provider-agnostic with deterministic fallback to reduce pipeline brittleness.
- Release gates convert evaluation signals into deploy decisions consumable by CI pipelines.
- Workspace-aware auth allows one platform to support multiple teams with scoped data.

## Scale Path

- Move to managed Postgres and Redis for durability.
- Run dedicated worker replicas for async eval throughput.
- Add queue priority and retry policies for long-running judge calls.
- Add OpenTelemetry export and dashboard alerts for SLO enforcement.
