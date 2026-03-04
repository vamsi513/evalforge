from datetime import datetime
from statistics import mean
from typing import Union

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import ReleaseGateDecisionRecord
from app.models.eval_run import EvalRunResponse, ReleaseGateCreate, ReleaseGateResponse
from app.services.eval_service import eval_service


class ReleaseGateService:
    def list_decisions(self, db: Session) -> list[ReleaseGateResponse]:
        try:
            rows = db.execute(
                select(ReleaseGateDecisionRecord).order_by(ReleaseGateDecisionRecord.created_at.desc())
            ).scalars().all()
        except OperationalError as exc:
            if "release_gate_decisions" not in str(exc):
                raise
            self._ensure_legacy_table(db)
            rows = db.execute(
                select(ReleaseGateDecisionRecord).order_by(ReleaseGateDecisionRecord.created_at.desc())
            ).scalars().all()
        return [self._to_response(row) for row in rows]

    def create_decision(self, db: Session, payload: ReleaseGateCreate) -> ReleaseGateResponse:
        baseline = eval_service.get_run_by_id(db, payload.baseline_run_id)
        candidate = eval_service.get_run_by_id(db, payload.candidate_run_id)

        if baseline is None or candidate is None:
            raise ValueError("Baseline or candidate run was not found")
        if baseline.dataset_name != payload.dataset_name or candidate.dataset_name != payload.dataset_name:
            raise ValueError("Both runs must belong to the provided dataset")

        metrics = self._build_metrics(baseline, candidate)
        failures = self._build_failures(payload, metrics)
        status = "passed" if not failures else "failed"
        summary = self._build_summary(status, baseline, candidate, failures)

        row = ReleaseGateDecisionRecord(
            dataset_name=payload.dataset_name,
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
            if "release_gate_decisions" not in str(exc):
                raise
            self._ensure_legacy_table(db)
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._to_response(row)

    @staticmethod
    def _build_metrics(
        baseline: EvalRunResponse, candidate: EvalRunResponse
    ) -> dict[str, Union[float, int]]:
        baseline_failed = sum(1 for result in baseline.results if not result.passed)
        candidate_failed = sum(1 for result in candidate.results if not result.passed)
        baseline_latency = mean(result.latency_ms for result in baseline.results) if baseline.results else 0.0
        candidate_latency = mean(result.latency_ms for result in candidate.results) if candidate.results else 0.0
        baseline_cost = sum(result.cost_usd for result in baseline.results)
        candidate_cost = sum(result.cost_usd for result in candidate.results)

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
        }

    @staticmethod
    def _build_failures(
        payload: ReleaseGateCreate, metrics: dict[str, Union[float, int]]
    ) -> list[dict[str, str]]:
        failures: list[dict[str, str]] = []

        if float(metrics["score_delta"]) < payload.min_score_delta:
            failures.append(
                {
                    "metric": "score_delta",
                    "reason": (
                        f"Candidate score delta {metrics['score_delta']} is below "
                        f"minimum threshold {payload.min_score_delta}."
                    ),
                }
            )
        if float(metrics["latency_delta_ms"]) > payload.max_latency_regression_ms:
            failures.append(
                {
                    "metric": "latency_delta_ms",
                    "reason": (
                        f"Candidate latency regression {metrics['latency_delta_ms']}ms exceeds "
                        f"threshold {payload.max_latency_regression_ms}ms."
                    ),
                }
            )
        if float(metrics["cost_delta_usd"]) > payload.max_cost_regression_usd:
            failures.append(
                {
                    "metric": "cost_delta_usd",
                    "reason": (
                        f"Candidate cost regression {metrics['cost_delta_usd']} exceeds "
                        f"threshold {payload.max_cost_regression_usd}."
                    ),
                }
            )
        if int(metrics["failed_case_delta"]) > payload.max_failed_case_delta:
            failures.append(
                {
                    "metric": "failed_case_delta",
                    "reason": (
                        f"Candidate failed-case delta {metrics['failed_case_delta']} exceeds "
                        f"threshold {payload.max_failed_case_delta}."
                    ),
                }
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
    def _to_response(row: ReleaseGateDecisionRecord) -> ReleaseGateResponse:
        return ReleaseGateResponse(
            id=row.id,
            dataset_name=row.dataset_name,
            baseline_run_id=row.baseline_run_id,
            candidate_run_id=row.candidate_run_id,
            status=row.status,
            summary=row.summary,
            metrics=row.metrics or {},
            failures=row.failures or [],
            created_at=row.created_at,
        )

    @staticmethod
    def _ensure_legacy_table(db: Session) -> None:
        inspector = inspect(db.bind)
        if "release_gate_decisions" in inspector.get_table_names():
            return
        db.execute(
            text(
                """
                CREATE TABLE release_gate_decisions (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    dataset_name VARCHAR(100) NOT NULL,
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
