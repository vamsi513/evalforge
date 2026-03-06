# Recruiter Demo Walkthrough (5 Minutes)

This walkthrough is optimized for recruiter and hiring-manager screens where you need to show platform depth quickly.

## 0:00 - 0:30 Problem Framing

Say:

"EvalForge is an LLM evaluation and release-gating platform. It helps teams prevent prompt and model regressions before production by combining golden datasets, structured judging, async batch evaluation, and deploy decisions."

## 0:30 - 1:30 API Surface and Platform Scope

Open Swagger at:

- `http://127.0.0.1:8001/docs`

Show these groups:

- `assets`: prompt templates, golden cases, dataset bundles
- `evals`: sync evals, async eval jobs, compare, judge
- `experiments`: experiment registry, reporting, promotion
- `release-gates`: policy checks, CI decision, schedules, trends
- `telemetry`: quality + latency + cost

Highlight:

"This is not a chat wrapper. It is an internal LLM reliability platform with gates and operational APIs."

## 1:30 - 2:30 Execute Reliability Flow

In Swagger, run:

1. `POST /api/v1/evals/stored`
2. `POST /api/v1/evals/compare`
3. `POST /api/v1/evals/judge`
4. `POST /api/v1/evals/async`
5. `GET /api/v1/evals/jobs/{job_id}`

Explain:

- stored eval validates prompt/model on persistent golden cases
- compare detects quality regressions between candidates
- judge adds structured quality signals
- async job path proves batch readiness

## 2:30 - 3:30 Release Gate and CI Story

Run and show:

1. `POST /api/v1/release-gates/evaluate-latest`
2. `GET /api/v1/release-gates/ci-decision`
3. `GET /api/v1/release-gates/policy-report`
4. `GET /api/v1/release-gates/trends`

Say:

"This creates a deployment verdict from score, latency, and cost deltas, so CI can block risky releases automatically."

Mention workflow artifact:

- `.github/workflows/release-gate-ci.yml`

## 3:30 - 4:30 Dashboard Evidence

Open:

- `http://localhost:8502`

Show:

- top metrics (runs, average score, latency, cost)
- Jobs tab with async status lifecycle
- release gate summaries and policy/drift views
- experiment promotion history

## 4:30 - 5:00 Close

Say:

"I designed this as a modular evaluation platform: assets, eval execution, judge scoring, release gating, async scheduling, and observability are decoupled so teams can evolve each component independently."

## Optional Technical Deep-Dive Prompts

- "How would you replace local async with durable workers?"
- "How do you calibrate judge-based scores over time?"
- "How do you prevent policy drift from causing false gate failures?"
- "How would you multi-tenant this for many product teams?"
