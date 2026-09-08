# EvalForge

[![CI](https://github.com/vamsi513/evalforge/actions/workflows/ci.yml/badge.svg)](https://github.com/vamsi513/evalforge/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

A production-inspired LLM evaluation platform with deterministic multi-signal scoring, experiment tracking, and automated release gates. Built with FastAPI, Next.js 16, and SQLAlchemy — deployed on AWS EC2 and Vercel.

## Live Demo

**Dashboard:** [https://evalforge-platform.vercel.app](https://evalforge-platform.vercel.app)

**API docs:** [http://23.21.42.197:8001/docs](http://23.21.42.197:8001/docs)

Click **Run General Knowledge** on the dashboard to run a live heuristic evaluation — no setup needed. The demo runs in `mock` judge mode (see [Judge modes](#judge-modes) below), so the compute cost shown is genuinely `$0.0000` — no LLM judge API call is made, only the deterministic scorers.

![EvalForge Overview — live demo with heuristic scores, pass rate, and latency](docs/screenshot.png)

## What it does

Teams shipping LLM features hit the same problems:

- prompt changes silently degrade output quality
- no reusable golden dataset for regression testing
- evaluation logic is inconsistent across teams
- latency and cost are untracked
- failures surface only after deployment

EvalForge addresses this with a full evaluation pipeline:

- **5-signal heuristic scorer** — keyword match, reference overlap, rubric coverage, structured output validation, lexical groundedness
- **LLM judge adapters** — OpenAI, Anthropic, Mistral via a unified interface with automatic heuristic fallback
- **Experiment leaderboard** — rank prompt versions and model configs by average eval score
- **Release gates** — PASS/FAIL CI signal based on score delta vs. baseline
- **Async job worker** — background eval jobs off the request/response cycle; runs in-process by default (`ASYNC_BACKEND=local`, what the live deployment uses today), with a Redis-backed queue available via `ASYNC_BACKEND=redis` for true multi-process decoupling
- **Telemetry** — per-run latency, cost, pass rate, and groundedness metrics

## Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, Pydantic, SQLAlchemy |
| Storage | SQLite (default), Postgres-ready, Alembic migrations |
| LLM judges | OpenAI · Anthropic · Mistral with heuristic fallback |
| Experiment tracking | MLflow — every eval run and pairwise comparison logged automatically (params, metrics, results artifact) |
| Async jobs | In-process by default (`ASYNC_BACKEND=local`); Redis-backed queue available for true decoupling |
| Frontend | Next.js 16 App Router, React, Vercel |
| Infrastructure | Docker, GitHub Actions CI/CD, AWS EC2 |

## Architecture

```text
┌─────────────────────────┐
│  Next.js 16 Dashboard   │  ← evalforge-platform.vercel.app
│  (Vercel)               │
└────────────┬────────────┘
             │ HTTPS (server-side proxy)
             ▼
┌────────────────────────────────────────────┐
│              FastAPI Backend               │  ← EC2 :8001
│  /evals  /experiments  /release-gates      │
│  /datasets  /telemetry  /evals/async       │
└──────┬─────────────────────────┬───────────┘
       │                         │
       ▼                         ▼
┌──────────────┐       ┌─────────────────────┐
│  Eval Engine │       │    Judge Engine      │
│  heuristic   │       │  OpenAI / Anthropic  │
│  5-signal    │       │  Mistral / fallback  │
└──────┬───────┘       └──────────┬──────────┘
       └──────────────┬───────────┘
                      ▼
             ┌────────────────┐
             │  SQLAlchemy    │
             │  SQLite / PG   │
             └────────────────┘
```

## Project structure

```text
evalforge/
├── app/                    # FastAPI backend
│   ├── api/routes/         # Evals, experiments, gates, telemetry
│   ├── engine/judge.py     # Heuristic + LLM judge scorers
│   ├── models/             # Pydantic schemas
│   └── services/           # Business logic
├── frontend/               # Next.js 16 dashboard
│   ├── app/                # App Router pages + loading skeletons
│   ├── components/         # MetricCard, ScoreChart, DemoButton…
│   └── lib/api.ts          # Typed API client
├── tests/
├── alembic/                # DB migrations
├── docker-compose.yml
└── Dockerfile
```

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Create `.env`:

```env
DATABASE_URL=sqlite:///./evalforge.db
AUTO_CREATE_TABLES=true
JUDGE_PROVIDER=mock
OPENAI_API_KEY=
JUDGE_MODEL=gpt-4o-mini
PLATFORM_API_KEY=
DEFAULT_WORKSPACE_ID=default
```

Start the API:

```bash
uvicorn app.main:app --port 8001
```

Start the frontend:

```bash
cd frontend && npm install && npm run dev
```

## Judge modes

| Provider | Description |
|---|---|
| `mock` | Deterministic heuristic scoring — no API key, zero cost, fast CI |
| `openai` | OpenAI structured judge via `/chat/completions` with JSON schema output |
| `anthropic` | Anthropic Messages API judge |
| `mistral` | Mistral client judge |
| `ollama` | Local judge via a self-hosted Ollama server (`qwen2.5:7b-instruct` by default) — no API key, no per-request cost, same JSON-schema request shape as the OpenAI judge since Ollama's endpoint is OpenAI-compatible |

All providers fall back to `mock` if the key is missing (not applicable to `ollama`, which has none) or the response is malformed. Fallback responses are marked with `used_fallback=true`.

### Judge provider benchmark

Measured against a 60-case evaluation set (`evaluation/judge_benchmark_dataset.json`, version `1.1.0` — 20 cases each across general knowledge, customer support, and code/tech, with deliberately mixed answer quality so scores actually differentiate). Every number below is a real per-request measurement — latency is wall-clock time around the actual API call (or local inference call), cost is computed from real token usage against the published per-token pricing in `app/engine/judge.py`. Reproduce with:

```bash
python -m scripts.run_judge_benchmark --out results.json
python -m scripts.analyze_judge_agreement results.json
python -m scripts.generate_eval_report
```

| Provider | Model | Latency (avg) | Total cost (60 calls) | Avg score | 95% CI |
|---|---|---|---|---|---|
| OpenAI | gpt-4o-mini | 1529 ms | $0.006674 | 0.645 | [0.548, 0.742] |
| Anthropic | claude-haiku-4-5 | 4162 ms | $0.184357 | 0.634 | [0.542, 0.727] |
| Ollama (local) | qwen2.5:7b-instruct | 6076 ms | local inference, no per-request API charge | 0.715 | [0.642, 0.782] |
| Mistral | mistral-small-latest | — | 0 real calls | — | — |

Total real spend for this benchmark: **$0.191031**. Mistral returned 0/60 real results — every call, and a second slower-paced retry, fell back to the mock judge under rate limiting rather than reaching the API; it's excluded from the table above rather than backfilled with a guess.

The three CIs overlap substantially at n=60 — these judges' average scores aren't statistically distinguishable from each other at this sample size. Local inference is markedly slower on this machine's CPU (roughly 4-5x OpenAI's latency) with no accuracy tradeoff visible in this benchmark.

**Local-vs-paid agreement** (pass/fail label, threshold score ≥0.7, same 60 shared cases):

| Comparison | % Agreement | Cohen's kappa | Pearson r (raw scores) |
|---|---|---|---|
| Ollama vs OpenAI | 93.3% | 0.859 | 0.786 |
| Ollama vs Anthropic | 91.7% | 0.822 | 0.824 |

Both kappa values fall in the "almost perfect agreement" band on the standard scale — a real result on 60 cases, not a large-scale claim.

**Position-bias test**: 15 hand-authored pairs (`evaluation/position_bias_pairs.json`, each with an unambiguously better and worse response to the same prompt), tested with the local judge in both orders via `scripts/run_position_bias_test.py`. **0/15 verdicts flipped on swap.** These pairs were deliberately easy calls; this doesn't establish anything about bias on close judgment calls.

60 cases is a small hand-written benchmark, not a comprehensive evaluation suite; treat every number above as a signal on this specific dataset, not a general quality ranking.

## Evaluator profiles

`POST /api/v1/evals` accepts `evaluator_profile`: `strict` | `balanced` | `lenient`

Profiles weight keyword hit, reference overlap, rubric coverage, structured output validity, and lexical groundedness differently.

## Async jobs

Background eval execution with persisted job state (`queued → running → completed → failed`).

```bash
# Redis-backed worker
ASYNC_BACKEND=redis
python -m app.workers.redis_worker
```

## CI/CD

Every push to `main`:

1. Ruff lint + security scan
2. Docker build
3. Full test suite
4. SSH deploy to EC2 — rebuild and restart container
5. Health check loop with automatic rollback on failure

Release gate CI workflow queries `GET /api/v1/release-gates/ci-decision` and fails the pipeline when `allow_deploy=false`.

SSH on the host is locked to a single home IP, not open to the internet. Since the GitHub-hosted runner's IP is different on every run, the deploy job authorizes its own runner's IP on port 22 immediately before connecting, then revokes that access in a cleanup step that runs even if the deploy fails — so the actual open window is the length of one deploy, not standing access.

## Infrastructure

The EC2 host, its security group, and its Elastic IP are managed as Terraform under `infra/` (`aws_instance`, `aws_security_group`, `aws_eip`). The host was originally provisioned by hand, so this was built by importing the real, running resources into Terraform state (`terraform import`) rather than standing up new ones — `terraform plan` against it returns no changes.

The instance is shared with two other deployed projects (AgentIQ, IncidentMemoryAI) running as separate containers on the same box, which is why the security group has ports for all three. `infra/main.tf` documents the actual bootstrap script, root volume, and every open port; `infra/variables.tf` exposes the SSH-source CIDR, key pair name, and instance type as variables instead of hardcoded values.

Not managed by Terraform: the nginx reverse proxy config on the host (edited directly over SSH, not version-controlled) and the Docker containers themselves (handled by the CI/CD deploy step above). The per-run SSH allowlisting in the deploy job also isn't Terraform state — it's a temporary rule added and removed outside Terraform's management on every deploy, by design.

## API surface

```
GET  /health
POST /api/v1/datasets
POST /api/v1/evals
POST /api/v1/evals/async
GET  /api/v1/evals/jobs/{job_id}
POST /api/v1/experiments
GET  /api/v1/experiments/leaderboard
POST /api/v1/release-gates
GET  /api/v1/release-gates/ci-decision
GET  /api/v1/telemetry/summary
```

Full reference: [http://23.21.42.197:8001/docs](http://23.21.42.197:8001/docs)

## License

MIT
