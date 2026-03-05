# EvalGate Roadmap

This document defines how the current `EvalForge` repo evolves into `EvalGate`, an internal-grade LLM evaluation and release-gating platform.

## Current State

The repo already supports:

- dataset and prompt asset storage
- golden cases
- synchronous and asynchronous eval runs
- judge-backed evaluations
- pairwise comparisons
- telemetry and dashboard views
- release-gate decisions

## Platform Direction

The next upgrades focus on turning prototype workflows into platform workflows:

1. dataset registry with scenario and slice metadata
2. evaluator registry instead of single-file scoring logic
3. experiment tracking metadata on every run
4. baseline versus candidate release policies
5. durable worker-backed batch execution
6. auth and workspace isolation

## Phase 1: Registry and Metadata

- add scenario, slice, and severity metadata to golden cases
- expose slice-aware reporting
- persist evaluator version and experiment metadata on runs

## Phase 2: Evaluator Framework

- define evaluator registry
- support rubric evaluators
- support schema validators
- support judge evaluators
- add hallucination and groundedness evaluators later

## Phase 3: Release Policies

- compare baseline vs candidate at dataset level
- add scenario-level threshold checks
- add slice-level threshold checks
- add critical-case blocking rules

## Phase 4: Batch Platform

- replace in-process background tasks with Redis-backed workers
- support replayable historical benchmark runs
- schedule nightly regressions

## Phase 5: Multi-Team Platform

- add API key auth
- add workspace or team ownership
- add audit history for benchmark changes

## Near-Term Deliverables

The near-term goal is to keep the current repo stable while making the internal architecture more modular:

- `app/engine/evaluator_registry.py`
- scenario metadata on golden cases
- persisted release decisions
- architecture and roadmap docs

## Long-Term Goal

`EvalGate` should become a CI-integrated platform that answers:

- Did the candidate prompt/model regress?
- On which scenarios did it regress?
- Is it slower or more expensive?
- Should this release be blocked?
