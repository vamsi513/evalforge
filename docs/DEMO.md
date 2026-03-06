# EvalForge Demo Script

## Goal

Show that EvalForge is not just an LLM wrapper. It is an evaluation system with reusable assets, quality scoring, async execution, and observability.

## Prerequisites

- API running on `http://127.0.0.1:8001`
- Dashboard running on `http://localhost:8502`
- Dashboard sidebar pointing to `http://127.0.0.1:8001`

## 5 minute walkthrough

### 1. Show the dashboard first

Point out:

- total runs
- average score
- total cost
- average latency
- queued / running / completed / failed jobs

Then open the `Jobs` tab.

### 2. Show prompt and golden asset management

In Swagger:

- `POST /api/v1/datasets`
- `POST /api/v1/assets/prompts`
- `POST /api/v1/assets/golden-cases`

Explain that prompt assets and golden datasets are versioned inputs to evaluation, not hardcoded examples.

### 3. Run a stored evaluation

Use `POST /api/v1/evals/stored`.

Explain that this is the baseline regression path for prompt changes.

### 4. Run a pairwise comparison

Use `POST /api/v1/evals/compare`.

Explain that this is the workflow for deciding whether prompt version B is better than prompt version A.

### 5. Run a judge-based evaluation

Use `POST /api/v1/evals/judge`.

Explain:

- mock judge for deterministic local use
- OpenAI-compatible structured judge for live evaluation
- safe fallback if provider output fails

### 6. Run an async evaluation

Use `POST /api/v1/evals/async`.

Copy the `job_id`, then poll:

- `GET /api/v1/evals/jobs/{job_id}`

Show the job moving to `completed`.

### 7. Return to dashboard

Refresh the dashboard and show:

- completed job count increased
- job appears in `Jobs`
- result appears in `Runs`

## Interview close

Use this line:

"I built EvalForge to solve the operational side of LLM systems: regression control, judge-based scoring, asset versioning, async execution, and dashboard observability."
