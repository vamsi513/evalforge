from datetime import datetime
from statistics import mean
from typing import Any, Union

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import ReleaseGateDecisionRecord
from app.models.eval_run import (
    EvalRunResponse,
    ReleaseGateCreate,
    ReleaseGateResponse,
    ReleaseGateSummaryResponse,
)
from app.services.eval_service import eval_service


class ReleaseGateService:
    def list_decisions(self, db: Session, workspace_id: str = "default") -> list[ReleaseGateResponse]:
        try:
            rows = db.execute(
                select(ReleaseGateDecisionRecord)
                .where(ReleaseGateDecisionRecord.workspace_id == workspace_id)
                .order_by(ReleaseGateDecisionRecord.created_at.desc())
            ).scalars().all()
        except OperationalError as exc:
            if "release_gate_decisions" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_legacy_table(db)
            rows = db.execute(
                select(ReleaseGateDecisionRecord)
                .where(ReleaseGateDecisionRecord.workspace_id == workspace_id)
                .order_by(ReleaseGateDecisionRecord.created_at.desc())
            ).scalars().all()
        return [self._to_response(row) for row in rows]

    def create_decision(
        self, db: Session, payload: ReleaseGateCreate, workspace_id: str = "default"
    ) -> ReleaseGateResponse:
        baseline = eval_service.get_run_by_id(db, payload.baseline_run_id, workspace_id=workspace_id)
        candidate = eval_service.get_run_by_id(db, payload.candidate_run_id, workspace_id=workspace_id)

        if baseline is None or candidate is None:
            raise ValueError("Baseline or candidate run was not found")
        if baseline.dataset_name != payload.dataset_name or candidate.dataset_name != payload.dataset_name:
            raise ValueError("Both runs must belong to the provided dataset")

        metrics = self._build_metrics(baseline, candidate)
        failures = self._build_failures(payload, metrics)
        status = "passed" if not failures else "failed"
        summary = self._build_summary(status, baseline, candidate, failures)
        experiment_name = self._resolve_experiment_name(payload, baseline, candidate)

        row = ReleaseGateDecisionRecord(
            dataset_name=payload.dataset_name,
            workspace_id=workspace_id,
            experiment_name=experiment_name,
            baseline_run_id=payload.baseline_run_id,
            candidate_run_id=payload.candidate_run_id,
            status=status,
            summary=summary,
            metrics=metrics,
            failures=failures,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except OperationalError as exc:
            db.rollback()
            if "release_gate_decisions" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_legacy_table(db)
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._to_response(row)

    def get_latest_summary(
        self,
        db: Session,
        dataset_name: str,
        workspace_id: str = "default",
        experiment_name: str = "",
    ) -> ReleaseGateSummaryResponse:
        try:
            query = (
                select(ReleaseGateDecisionRecord)
                .where(
                    ReleaseGateDecisionRecord.workspace_id == workspace_id,
                    ReleaseGateDecisionRecord.dataset_name == dataset_name,
                )
                .order_by(ReleaseGateDecisionRecord.created_at.desc())
            )
            if experiment_name:
                query = query.where(ReleaseGateDecisionRecord.experiment_name == experiment_name)
            row = db.execute(query.limit(1)).scalar_one_or_none()
        except OperationalError as exc:
            if "release_gate_decisions" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_legacy_table(db)
            query = (
                select(ReleaseGateDecisionRecord)
                .where(
                    ReleaseGateDecisionRecord.workspace_id == workspace_id,
                    ReleaseGateDecisionRecord.dataset_name == dataset_name,
                )
                .order_by(ReleaseGateDecisionRecord.created_at.desc())
            )
            if experiment_name:
                query = query.where(ReleaseGateDecisionRecord.experiment_name == experiment_name)
            row = db.execute(query.limit(1)).scalar_one_or_none()

        if row is None:
            return ReleaseGateSummaryResponse(
                dataset_name=dataset_name,
                workspace_id=workspace_id,
                experiment_name=experiment_name,
                status="not_evaluated",
                gate_passed=False,
                summary="No release-gate decision found for the requested scope.",
            )

        metrics = row.metrics or {}
        failures = row.failures or []
        return ReleaseGateSummaryResponse(
            dataset_name=row.dataset_name,
            workspace_id=getattr(row, "workspace_id", "default"),
            experiment_name=getattr(row, "experiment_name", "") or experiment_name,
            decision_id=row.id,
            status=row.status,
            gate_passed=row.status == "passed",
            summary=row.summary,
            blocking_failure_codes=[failure.get("code", "") for failure in failures if failure.get("code")],
            blocking_failures=[failure.get("reason", "") for failure in failures if failure.get("reason")],
            score_delta=float(metrics.get("score_delta", 0.0)),
            failed_case_delta=int(metrics.get("failed_case_delta", 0)),
            scenario_failed_delta=int(metrics.get("scenario_failed_delta", 0)),
            slice_failed_delta=int(metrics.get("slice_failed_delta", 0)),
            decided_at=row.created_at,
        )

    @staticmethod
    def _build_metrics(
        baseline: EvalRunResponse, candidate: EvalRunResponse
    ) -> dict[str, Any]:
        baseline_failed = sum(1 for result in baseline.results if not result.passed)
        candidate_failed = sum(1 for result in candidate.results if not result.passed)
        baseline_latency = mean(result.latency_ms for result in baseline.results) if baseline.results else 0.0
        candidate_latency = mean(result.latency_ms for result in candidate.results) if candidate.results else 0.0
        baseline_cost = sum(result.cost_usd for result in baseline.results)
        candidate_cost = sum(result.cost_usd for result in candidate.results)
        scenario_metrics = ReleaseGateService._build_scenario_metrics(baseline, candidate)
        slice_metrics = ReleaseGateService._build_slice_metrics(baseline, candidate)
        scenario_failed_delta = sum(
            max(0, metric["candidate_failed_cases"] - metric["baseline_failed_cases"])
            for metric in scenario_metrics
        )
        slice_failed_delta = sum(
            max(0, metric["candidate_failed_cases"] - metric["baseline_failed_cases"])
            for metric in slice_metrics
        )

        return {
            "baseline_score": round(baseline.average_score, 6),
            "candidate_score": round(candidate.average_score, 6),
            "score_delta": round(candidate.average_score - baseline.average_score, 6),
            "baseline_latency_ms": round(baseline_latency, 3),
            "candidate_latency_ms": round(candidate_latency, 3),
            "latency_delta_ms": round(candidate_latency - baseline_latency, 3),
            "baseline_cost_usd": round(baseline_cost, 6),
            "candidate_cost_usd": round(candidate_cost, 6),
            "cost_delta_usd": round(candidate_cost - baseline_cost, 6),
            "baseline_failed_cases": baseline_failed,
            "candidate_failed_cases": candidate_failed,
            "failed_case_delta": candidate_failed - baseline_failed,
            "scenario_failed_delta": scenario_failed_delta,
            "slice_failed_delta": slice_failed_delta,
            "scenario_metrics": scenario_metrics,
            "slice_metrics": slice_metrics,
        }

    @staticmethod
    def _build_failures(
        payload: ReleaseGateCreate, metrics: dict[str, Any]
    ) -> list[dict[str, str]]:
        failures: list[dict[str, str]] = []

        def add_failure(code: str, metric: str, reason: str) -> None:
            failures.append({"code": code, "metric": metric, "reason": reason})

        if float(metrics["score_delta"]) < payload.min_score_delta:
            add_failure(
                code="SCORE_DELTA_FAIL",
                metric="score_delta",
                reason=(
                    f"Candidate score delta {metrics['score_delta']} is below "
                    f"minimum threshold {payload.min_score_delta}."
                ),
            )
        if float(metrics["latency_delta_ms"]) > payload.max_latency_regression_ms:
            add_failure(
                code="LATENCY_DELTA_FAIL",
                metric="latency_delta_ms",
                reason=(
                    f"Candidate latency regression {metrics['latency_delta_ms']}ms exceeds "
                    f"threshold {payload.max_latency_regression_ms}ms."
                ),
            )
        if float(metrics["cost_delta_usd"]) > payload.max_cost_regression_usd:
            add_failure(
                code="COST_DELTA_FAIL",
                metric="cost_delta_usd",
                reason=(
                    f"Candidate cost regression {metrics['cost_delta_usd']} exceeds "
                    f"threshold {payload.max_cost_regression_usd}."
                ),
            )
        if int(metrics["failed_case_delta"]) > payload.max_failed_case_delta:
            add_failure(
                code="FAILED_CASE_DELTA_FAIL",
                metric="failed_case_delta",
                reason=(
                    f"Candidate failed-case delta {metrics['failed_case_delta']} exceeds "
                    f"threshold {payload.max_failed_case_delta}."
                ),
            )
        if int(metrics["scenario_failed_delta"]) > payload.max_scenario_failed_delta:
            add_failure(
                code="SCENARIO_FAILED_DELTA_FAIL",
                metric="scenario_failed_delta",
                reason=(
                    f"Scenario failed-case delta {metrics['scenario_failed_delta']} exceeds "
                    f"threshold {payload.max_scenario_failed_delta}."
                ),
            )
        for scenario_metric in metrics.get("scenario_metrics", []):
            if float(scenario_metric["score_delta"]) < payload.min_score_delta:
                add_failure(
                    code="SCENARIO_SCORE_DELTA_FAIL",
                    metric=f"scenario:{scenario_metric['scenario']}",
                    reason=(
                        f"Scenario {scenario_metric['scenario']} score delta "
                        f"{scenario_metric['score_delta']} is below threshold {payload.min_score_delta}."
                    ),
                )
        for scenario_metric in metrics.get("scenario_metrics", []):
            scenario_name = str(scenario_metric["scenario"])
            score_threshold = payload.scenario_score_thresholds.get(scenario_name)
            if score_threshold is not None and float(scenario_metric["score_delta"]) < score_threshold:
                add_failure(
                    code="SCENARIO_SCORE_THRESHOLD_FAIL",
                    metric=f"scenario_score_threshold:{scenario_name}",
                    reason=(
                        f"Scenario {scenario_name} score delta {scenario_metric['score_delta']} "
                        f"is below scenario threshold {score_threshold}."
                    ),
                )
            failed_threshold = payload.scenario_failed_case_thresholds.get(scenario_name)
            scenario_failed_delta = int(scenario_metric["candidate_failed_cases"]) - int(
                scenario_metric["baseline_failed_cases"]
            )
            if failed_threshold is not None and scenario_failed_delta > failed_threshold:
                add_failure(
                    code="SCENARIO_FAILED_THRESHOLD_FAIL",
                    metric=f"scenario_failed_threshold:{scenario_name}",
                    reason=(
                        f"Scenario {scenario_name} failed-case delta {scenario_failed_delta} "
                        f"exceeds scenario threshold {failed_threshold}."
                    ),
                )
        for slice_metric in metrics.get("slice_metrics", []):
            slice_name = str(slice_metric["slice_name"])
            score_threshold = payload.slice_score_thresholds.get(slice_name)
            if score_threshold is not None and float(slice_metric["score_delta"]) < score_threshold:
                add_failure(
                    code="SLICE_SCORE_THRESHOLD_FAIL",
                    metric=f"slice_score_threshold:{slice_name}",
                    reason=(
                        f"Slice {slice_name} score delta {slice_metric['score_delta']} "
                        f"is below slice threshold {score_threshold}."
                    ),
                )
            failed_threshold = payload.slice_failed_case_thresholds.get(slice_name)
            slice_failed_delta = int(slice_metric["candidate_failed_cases"]) - int(
                slice_metric["baseline_failed_cases"]
            )
            if failed_threshold is not None and slice_failed_delta > failed_threshold:
                add_failure(
                    code="SLICE_FAILED_THRESHOLD_FAIL",
                    metric=f"slice_failed_threshold:{slice_name}",
                    reason=(
                        f"Slice {slice_name} failed-case delta {slice_failed_delta} "
                        f"exceeds slice threshold {failed_threshold}."
                    ),
                )
        return failures

    @staticmethod
    def _build_summary(
        status: str,
        baseline: EvalRunResponse,
        candidate: EvalRunResponse,
        failures: list[dict[str, str]],
    ) -> str:
        if status == "passed":
            return (
                f"Candidate run {candidate.id} passed release gating against baseline {baseline.id} "
                "with no threshold regressions."
            )
        return (
            f"Candidate run {candidate.id} failed release gating against baseline {baseline.id}. "
            f"{len(failures)} threshold regression(s) detected."
        )

    @staticmethod
    def _resolve_experiment_name(
        payload: ReleaseGateCreate,
        baseline: EvalRunResponse,
        candidate: EvalRunResponse,
    ) -> str:
        if payload.experiment_name:
            return payload.experiment_name
        if candidate.experiment_name and candidate.experiment_name == baseline.experiment_name:
            return candidate.experiment_name
        return candidate.experiment_name or baseline.experiment_name or ""

    @staticmethod
    def _to_response(row: ReleaseGateDecisionRecord) -> ReleaseGateResponse:
        return ReleaseGateResponse(
            id=row.id,
            dataset_name=row.dataset_name,
            workspace_id=getattr(row, "workspace_id", "default"),
            experiment_name=getattr(row, "experiment_name", ""),
            baseline_run_id=row.baseline_run_id,
            candidate_run_id=row.candidate_run_id,
            status=row.status,
            summary=row.summary,
            metrics=row.metrics or {},
            failures=row.failures or [],
            created_at=row.created_at,
        )

    @staticmethod
    def _build_scenario_metrics(
        baseline: EvalRunResponse, candidate: EvalRunResponse
    ) -> list[dict[str, Union[str, float, int]]]:
        scenario_metrics: list[dict[str, Union[str, float, int]]] = []
        scenarios = sorted(
            {
                result.scenario
                for result in baseline.results + candidate.results
                if getattr(result, "scenario", "general")
            }
        )
        for scenario in scenarios:
            baseline_results = [result for result in baseline.results if result.scenario == scenario]
            candidate_results = [result for result in candidate.results if result.scenario == scenario]
            baseline_score = mean(result.score for result in baseline_results) if baseline_results else 0.0
            candidate_score = mean(result.score for result in candidate_results) if candidate_results else 0.0
            baseline_failed = sum(1 for result in baseline_results if not result.passed)
            candidate_failed = sum(1 for result in candidate_results if not result.passed)
            scenario_metrics.append(
                {
                    "scenario": scenario,
                    "baseline_score": round(baseline_score, 6),
                    "candidate_score": round(candidate_score, 6),
                    "score_delta": round(candidate_score - baseline_score, 6),
                    "baseline_failed_cases": baseline_failed,
                    "candidate_failed_cases": candidate_failed,
                }
            )
        return scenario_metrics

    @staticmethod
    def _build_slice_metrics(
        baseline: EvalRunResponse, candidate: EvalRunResponse
    ) -> list[dict[str, Union[str, float, int]]]:
        slice_metrics: list[dict[str, Union[str, float, int]]] = []
        slices = sorted(
            {
                result.slice_name
                for result in baseline.results + candidate.results
                if getattr(result, "slice_name", "default")
            }
        )
        for slice_name in slices:
            baseline_results = [result for result in baseline.results if result.slice_name == slice_name]
            candidate_results = [result for result in candidate.results if result.slice_name == slice_name]
            baseline_score = mean(result.score for result in baseline_results) if baseline_results else 0.0
            candidate_score = mean(result.score for result in candidate_results) if candidate_results else 0.0
            baseline_failed = sum(1 for result in baseline_results if not result.passed)
            candidate_failed = sum(1 for result in candidate_results if not result.passed)
            slice_metrics.append(
                {
                    "slice_name": slice_name,
                    "baseline_score": round(baseline_score, 6),
                    "candidate_score": round(candidate_score, 6),
                    "score_delta": round(candidate_score - baseline_score, 6),
                    "baseline_failed_cases": baseline_failed,
                    "candidate_failed_cases": candidate_failed,
                }
            )
        return slice_metrics

    @staticmethod
    def _ensure_legacy_table(db: Session) -> None:
        inspector = inspect(db.bind)
        if "release_gate_decisions" in inspector.get_table_names():
            existing_columns = {column["name"] for column in inspector.get_columns("release_gate_decisions")}
            if "workspace_id" not in existing_columns:
                db.execute(
                    text(
                        "ALTER TABLE release_gate_decisions "
                        "ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'"
                    )
                )
            if "experiment_name" not in existing_columns:
                db.execute(
                    text(
                        "ALTER TABLE release_gate_decisions "
                        "ADD COLUMN experiment_name VARCHAR(100) NOT NULL DEFAULT ''"
                    )
                )
            existing_indexes = {index["name"] for index in inspector.get_indexes("release_gate_decisions")}
            if "ix_release_gate_decisions_workspace_id" not in existing_indexes:
                db.execute(
                    text("CREATE INDEX ix_release_gate_decisions_workspace_id ON release_gate_decisions (workspace_id)")
                )
            if "ix_release_gate_decisions_experiment_name" not in existing_indexes:
                db.execute(
                    text(
                        "CREATE INDEX ix_release_gate_decisions_experiment_name "
                        "ON release_gate_decisions (experiment_name)"
                    )
                )
            db.commit()
            return
        db.execute(
            text(
                """
                CREATE TABLE release_gate_decisions (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    dataset_name VARCHAR(100) NOT NULL,
                    workspace_id VARCHAR(100) NOT NULL DEFAULT 'default',
                    experiment_name VARCHAR(100) NOT NULL DEFAULT '',
                    baseline_run_id VARCHAR(36) NOT NULL,
                    candidate_run_id VARCHAR(36) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    summary TEXT NOT NULL,
                    metrics JSON NOT NULL,
                    failures JSON NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        db.execute(
            text("CREATE INDEX ix_release_gate_decisions_dataset_name ON release_gate_decisions (dataset_name)")
        )
        db.execute(
            text("CREATE INDEX ix_release_gate_decisions_workspace_id ON release_gate_decisions (workspace_id)")
        )
        db.execute(
            text("CREATE INDEX ix_release_gate_decisions_experiment_name ON release_gate_decisions (experiment_name)")
        )
        db.execute(
            text(
                "CREATE INDEX ix_release_gate_decisions_baseline_run_id "
                "ON release_gate_decisions (baseline_run_id)"
            )
        )
        db.execute(
            text(
                "CREATE INDEX ix_release_gate_decisions_candidate_run_id "
                "ON release_gate_decisions (candidate_run_id)"
            )
        )
        db.execute(
            text("CREATE INDEX ix_release_gate_decisions_status ON release_gate_decisions (status)")
        )
        db.commit()


release_gate_service = ReleaseGateService()
