"""
app/engine/mlflow_tracker.py — MLflow experiment tracking for EvalForge runs.

Wraps EvalRunner.run() and EvalRunner.compare() so every evaluation is logged
as an MLflow run with metrics, parameters, and a JSON artifact of all results.

Usage:
    from app.engine.mlflow_tracker import tracked_run, tracked_compare

Configuration (environment variables):
    MLFLOW_TRACKING_URI — MLflow server URI (default: local ./mlruns)
    MLFLOW_EXPERIMENT   — Experiment name (default: evalforge)
"""

import json
import logging
import os
import subprocess
import tempfile
from datetime import UTC, datetime

from app.engine.evaluator import EvalRunner
from app.models.eval_run import (
    EvalCaseResult,
    EvalRunCreate,
    PairwiseEvalCreate,
    PairwiseEvalResponse,
)

logger = logging.getLogger(__name__)

_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "evalforge")
_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "")

try:
    import mlflow
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False
    logger.warning("mlflow not installed — pip install mlflow to enable tracking")


def _git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _setup() -> None:
    if not _MLFLOW_AVAILABLE:
        return
    if _TRACKING_URI:
        mlflow.set_tracking_uri(_TRACKING_URI)
    mlflow.set_experiment(_EXPERIMENT)


def _log_artifact(data: dict) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="evalforge_run_"
    ) as f:
        json.dump(data, f, indent=2, default=str)
        path = f.name
    mlflow.log_artifact(path, artifact_path="results")
    os.unlink(path)


def tracked_run(
    runner: EvalRunner,
    payload: EvalRunCreate,
) -> tuple[list[EvalCaseResult], float]:
    """
    Run evaluation and log metrics + results to MLflow.

    Args:
        runner:  EvalRunner instance.
        payload: EvalRunCreate request payload.

    Returns:
        Same (results, avg_score) tuple as EvalRunner.run().
    """
    results, avg_score = runner.run(payload)

    if not _MLFLOW_AVAILABLE:
        return results, avg_score

    _setup()
    run_name = f"eval-{datetime.now(UTC):%Y%m%d-%H%M%S}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "dataset": payload.dataset_name if hasattr(payload, "dataset_name") else "inline",
            "evaluator_profile": payload.evaluator_profile,
            "num_samples": len(payload.samples),
            "git_sha": _git_sha(),
        })

        mlflow.log_metric("avg_score", avg_score)
        mlflow.log_metric("pass_rate", sum(1 for r in results if r.passed) / len(results) if results else 0.0)
        mlflow.log_metric("avg_latency_ms", sum(r.latency_ms for r in results) / len(results) if results else 0.0)
        mlflow.log_metric("avg_cost_usd", sum(r.cost_usd for r in results) / len(results) if results else 0.0)

        _log_artifact({
            "run_name": run_name,
            "avg_score": avg_score,
            "results": [r.model_dump() for r in results],
        })

        logger.info(
            "MLflow run '%s' — avg_score=%.4f pass_rate=%.2f",
            run_name,
            avg_score,
            sum(1 for r in results if r.passed) / len(results) if results else 0.0,
        )

    return results, avg_score


def tracked_compare(
    runner: EvalRunner,
    payload: PairwiseEvalCreate,
) -> PairwiseEvalResponse:
    """
    Run pairwise comparison and log win-rates + results to MLflow.

    Args:
        runner:  EvalRunner instance.
        payload: PairwiseEvalCreate request payload.

    Returns:
        Same PairwiseEvalResponse as EvalRunner.compare().
    """
    response = runner.compare(payload)

    if not _MLFLOW_AVAILABLE:
        return response

    _setup()
    run_name = f"pairwise-{datetime.now(UTC):%Y%m%d-%H%M%S}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "dataset": payload.dataset_name,
            "model": payload.model_name,
            "prompt_version_a": payload.prompt_version_a,
            "prompt_version_b": payload.prompt_version_b,
            "num_samples": len(payload.samples),
            "git_sha": _git_sha(),
        })

        mlflow.log_metric("win_rate_a", response.win_rate_a)
        mlflow.log_metric("win_rate_b", response.win_rate_b)
        mlflow.log_metric("ties", response.ties)

        _log_artifact({
            "run_name": run_name,
            "win_rate_a": response.win_rate_a,
            "win_rate_b": response.win_rate_b,
            "results": [r.model_dump() for r in response.results],
        })

        logger.info(
            "MLflow pairwise '%s' — win_a=%.2f win_b=%.2f ties=%d",
            run_name, response.win_rate_a, response.win_rate_b, response.ties,
        )

    return response
