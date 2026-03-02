# EvalForge

EvalForge is a production-style LLM Reliability and PromptOps platform for regression testing prompts, scoring model outputs, comparing prompt versions, managing golden datasets, and monitoring latency, cost, and async evaluation jobs.

## Why this project matters

Teams shipping LLM features usually fail on the same problems:

- prompt changes silently degrade quality
- there is no reusable golden dataset for regression checks
- evaluation logic is inconsistent across teams
- latency and cost are not tracked with output quality
- failures are only discovered after deployment

EvalForge addresses that by combining:

- FastAPI evaluation APIs
- persistent dataset, run, and asset management
- heuristic and LLM-judge scoring
- prompt template and golden case versioning
- async job submission and polling
- dashboard observability

## Key capabilities

- Golden dataset management with stored prompt templates and golden cases
- Synchronous eval runs for quick iteration
- Async eval jobs for background processing and job polling
- Pairwise comparison for prompt or response variants
- Judge-based scoring with structured OpenAI-compatible output and fallback
- Bundle import/export for dataset portability
- Telemetry for average score, latency, and cost
- Streamlit dashboard for runs, jobs, prompts, and golden assets

## Architecture

```text
                      +----------------------+
                      |  Streamlit Dashboard |
                      +----------+-----------+
                                 |
                                 v
+-----------+          +---------+----------+         +------------------+
| Swagger UI | ------> |      FastAPI       | ------> |  Telemetry APIs  |
+-----------+          |  evals / assets    |         +------------------+
                       |  jobs / datasets   |
                       +----+-----------+---+
                            |           |
                            |           +-------------------------------+
                            |                                           |
                            v                                           v
                   +--------+---------+                     +-----------+-----------+
                   |   Eval Engine    |                     |  Judge Engine         |
                   | heuristic scorer |                     | mock / OpenAI-style   |
                   +--------+---------+                     +-----------+-----------+
                            |                                           |
                            +------------------+------------------------+
                                               |
                                               v
                                   +-----------+-----------+
                                   |  SQLAlchemy Storage   |
                                   | runs / jobs / assets  |
                                   +-----------+-----------+
                                               |
                                               v
                                        SQLite or Postgres
```

## Stack

- Backend: FastAPI, Pydantic, SQLAlchemy
- Storage: SQLite by default, Postgres-ready config, Alembic migrations
- LLM judge: OpenAI-compatible structured `chat/completions` path with fallback
- Dashboard: Streamlit, pandas
- Async processing: background job submission + persisted job status
- Packaging: editable Python package with `pyproject.toml`

## Project structure

```text
evalforge/
├── app/
│   ├── api/routes/
│   ├── core/
│   ├── db/
│   ├── engine/
│   ├── models/
│   └── services/
├── dashboard/
├── training/
├── tests/
├── alembic/
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
└── README.md
```

## Quick start

```bash
cd "/Users/vamsi/Documents/AI PROJECT /evalforge"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[dev]'
```

Create or update `.env`:

```env
DATABASE_URL=sqlite:///./evalforge.db
AUTO_CREATE_TABLES=true
JUDGE_PROVIDER=mock
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
JUDGE_MODEL=gpt-4o-mini
```

Start the API:

```bash
python -m uvicorn app.main:app --port 8001
```

Open Swagger:

- [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

Start the dashboard in a second terminal:

```bash
cd "/Users/vamsi/Documents/AI PROJECT /evalforge"
source .venv/bin/activate
streamlit run dashboard/app.py --server.port 8502
```

Open dashboard:

- [http://localhost:8502](http://localhost:8502)

Set sidebar API URL to:

```text
http://127.0.0.1:8001
```

## Main API surface

- `GET /health`
- `GET /api/v1/datasets`
- `POST /api/v1/datasets`
- `GET /api/v1/assets/prompts`
- `POST /api/v1/assets/prompts`
- `GET /api/v1/assets/golden-cases`
- `POST /api/v1/assets/golden-cases`
- `GET /api/v1/assets/bundles/{dataset_name}`
- `POST /api/v1/assets/bundles/import`
- `GET /api/v1/evals`
- `POST /api/v1/evals`
- `POST /api/v1/evals/async`
- `GET /api/v1/evals/jobs`
- `GET /api/v1/evals/jobs/{job_id}`
- `POST /api/v1/evals/stored`
- `POST /api/v1/evals/judge`
- `POST /api/v1/evals/compare`
- `GET /api/v1/telemetry/summary`

## Demo flow

For a clean demo, use this order:

1. Create a dataset with `POST /api/v1/datasets`
2. Add a prompt template with `POST /api/v1/assets/prompts`
3. Add a golden case with `POST /api/v1/assets/golden-cases`
4. Run `POST /api/v1/evals/stored`
5. Run `POST /api/v1/evals/compare`
6. Run `POST /api/v1/evals/judge`
7. Run `POST /api/v1/evals/async`
8. Poll `GET /api/v1/evals/jobs/{job_id}`
9. Open the dashboard and show Runs + Jobs + Telemetry

## Judge modes

### Mock mode

Use deterministic local scoring:

```env
JUDGE_PROVIDER=mock
```

### OpenAI-compatible structured judge

```env
JUDGE_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
JUDGE_MODEL=gpt-4o-mini
```

Behavior:

- sends a structured JSON-schema scoring request to `/chat/completions`
- parses score, pass/fail, matched terms, missing terms, criterion scores, and reasoning
- falls back to the mock judge if the key is missing, the provider is unavailable, or the response is malformed
- marks fallback responses with `used_fallback=true`

## Async jobs

EvalForge supports background eval execution with persisted job state.

Job lifecycle:

- `queued`
- `running`
- `completed`
- `failed`

The dashboard surfaces:

- queued job count
- running job count
- completed job count
- failed job count
- per-job result payloads

## Dataset portability

Bundles let you move a dataset and its assets together:

- dataset record
- prompt templates
- golden cases

Use:

- `GET /api/v1/assets/bundles/{dataset_name}`
- `POST /api/v1/assets/bundles/import`

## Postgres and Alembic

The repo includes Alembic and a Postgres-ready Docker Compose file, but local SQLite is the default path.

Install dependencies:

```bash
cd "/Users/vamsi/Documents/AI PROJECT /evalforge"
source .venv/bin/activate
pip install -e '.[dev]'
```

Run migrations against the current database target:

```bash
alembic upgrade head
```

For Postgres later, switch `.env` to a Postgres URL and set:

```env
AUTO_CREATE_TABLES=false
```

## Resume-ready impact

- Built an end-to-end LLM evaluation platform with FastAPI, SQLAlchemy, Streamlit, and structured judge scoring instead of a thin API wrapper
- Designed reusable prompt template, golden-case, and dataset bundle workflows for regression testing and environment portability
- Implemented synchronous and asynchronous evaluation pipelines with persisted job state, polling, and dashboard observability
- Added OpenAI-compatible structured judging with JSON-schema parsing and deterministic fallback behavior for reliability
- Tracked evaluation quality alongside latency and cost to support production trade-off analysis

## Demo talking points

- "This project is about LLM reliability, not chat UX."
- "I separated prompt assets, eval runs, job execution, judge scoring, and telemetry so the system can evolve independently."
- "The async job layer shows how I would scale from interactive experimentation to batch regression runs."
- "The live judge path uses structured outputs with fallback because production evaluation pipelines cannot assume perfect provider behavior."

## Current limitations

- Async execution currently uses FastAPI background tasks rather than Redis/Celery workers
- Judge integration currently targets an OpenAI-compatible API shape only
- There is no auth or workspace isolation yet
- The training package is still scaffold-level and not yet integrated into the main scoring path

## Next upgrades

1. Replace in-process background jobs with Redis-backed workers
2. Add a trained quality predictor and calibration layer
3. Add CI regression gates for pull requests
4. Add auth, workspaces, and experiment history
5. Deploy API and dashboard publicly with managed Postgres
