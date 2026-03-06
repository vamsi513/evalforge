from datetime import datetime
from typing import Optional

from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import EvalRunRecord, ExperimentRecord, ReleaseGateDecisionRecord
from app.models.experiment import (
    ExperimentCreate,
    ExperimentGateTrend,
    ExperimentPromoteRequest,
    ExperimentPromoteResponse,
    ExperimentReport,
    ExperimentResponse,
    ExperimentRunTrend,
)


class ExperimentService:
    def list_experiments(self, db: Session, workspace_id: str) -> list[ExperimentResponse]:
        try:
            rows = db.execute(
                select(ExperimentRecord)
                .where(ExperimentRecord.workspace_id == workspace_id)
                .order_by(ExperimentRecord.updated_at.desc())
            ).scalars().all()
        except OperationalError as exc:
            if "experiments" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_experiments_table(db)
            rows = db.execute(
                select(ExperimentRecord)
                .where(ExperimentRecord.workspace_id == workspace_id)
                .order_by(ExperimentRecord.updated_at.desc())
            ).scalars().all()
        return [self._to_response(db, row) for row in rows]

    def create_experiment(self, db: Session, payload: ExperimentCreate, workspace_id: str) -> ExperimentResponse:
        row = ExperimentRecord(workspace_id=workspace_id, **payload.model_dump())
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except OperationalError as exc:
            db.rollback()
            if "experiments" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_experiments_table(db)
            row = ExperimentRecord(workspace_id=workspace_id, **payload.model_dump())
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._to_response(db, row)

    def get_experiment_report(self, db: Session, name: str, workspace_id: str) -> Optional[ExperimentReport]:
        try:
            row = db.execute(
                select(ExperimentRecord).where(
                    ExperimentRecord.name == name,
                    ExperimentRecord.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()
        except OperationalError as exc:
            if "experiments" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_experiments_table(db)
            row = db.execute(
                select(ExperimentRecord).where(
                    ExperimentRecord.name == name,
                    ExperimentRecord.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()
        if row is None:
            return None

        experiment = self._to_response(db, row)
        recent_runs = self._list_run_trends(db, row.workspace_id, row.dataset_name, row.name)
        gate_trends = self._list_gate_trends(db, row.workspace_id, row.dataset_name, row.name)
        return ExperimentReport(
            experiment=experiment,
            recent_runs=recent_runs,
            release_gates=gate_trends,
            score_trend=[run.average_score for run in recent_runs],
            latest_gate_status=gate_trends[0].status if gate_trends else "",
        )

    def exists(self, db: Session, name: str, workspace_id: str) -> bool:
        query = select(ExperimentRecord.id).where(
            ExperimentRecord.name == name,
            ExperimentRecord.workspace_id == workspace_id,
        )
        try:
            return db.execute(query).first() is not None
        except OperationalError as exc:
            if "experiments" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_experiments_table(db)
            return db.execute(query).first() is not None

    def promote_candidate(
        self, db: Session, name: str, payload: ExperimentPromoteRequest, workspace_id: str
    ) -> ExperimentPromoteResponse:
        try:
            experiment_row = db.execute(
                select(ExperimentRecord).where(
                    ExperimentRecord.name == name,
                    ExperimentRecord.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()
        except OperationalError as exc:
            if "experiments" not in str(exc) and "workspace_id" not in str(exc):
                raise
            self._ensure_experiments_table(db)
            experiment_row = db.execute(
                select(ExperimentRecord).where(
                    ExperimentRecord.name == name,
                    ExperimentRecord.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

        if experiment_row is None:
            raise ValueError("Experiment not found")

        latest_gate = db.execute(
            select(ReleaseGateDecisionRecord)
            .where(
                ReleaseGateDecisionRecord.workspace_id == workspace_id,
                ReleaseGateDecisionRecord.dataset_name == experiment_row.dataset_name,
                ReleaseGateDecisionRecord.experiment_name == experiment_row.name,
            )
            .order_by(ReleaseGateDecisionRecord.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_gate is None:
            raise ValueError("No release gate decision found for this experiment")

        if payload.require_latest_gate_passed and latest_gate.status != "passed":
            raise ValueError("Latest release gate did not pass; promotion blocked")

        promoted_run_id = payload.candidate_run_id or latest_gate.candidate_run_id
        if not promoted_run_id:
            raise ValueError("No candidate run available to promote")

        run_exists = db.execute(
            select(EvalRunRecord.id).where(
                EvalRunRecord.id == promoted_run_id,
                EvalRunRecord.workspace_id == workspace_id,
                EvalRunRecord.dataset_name == experiment_row.dataset_name,
                EvalRunRecord.experiment_name == experiment_row.name,
            )
        ).first()
        if run_exists is None:
            raise ValueError("Candidate run does not exist in this experiment scope")

        experiment_row.baseline_run_id = promoted_run_id
        experiment_row.candidate_run_id = ""
        experiment_row.status = "baseline"
        experiment_row.updated_at = datetime.utcnow()

        metadata = dict(experiment_row.experiment_metadata or {})
        metadata["last_promoted_gate_id"] = latest_gate.id
        metadata["last_promoted_at"] = datetime.utcnow().isoformat()
        experiment_row.experiment_metadata = metadata

        db.commit()
        db.refresh(experiment_row)

        updated_experiment = self._to_response(db, experiment_row)
        return ExperimentPromoteResponse(
            experiment_name=updated_experiment.name,
            workspace_id=updated_experiment.workspace_id,
            promoted_run_id=promoted_run_id,
            gate_id=latest_gate.id,
            gate_status=latest_gate.status,
            message=f"Promoted run {promoted_run_id} to baseline for experiment {updated_experiment.name}.",
            updated_experiment=updated_experiment,
        )

    @staticmethod
    def _to_response(db: Session, row: ExperimentRecord) -> ExperimentResponse:
        try:
            run_count = db.execute(
                select(func.count(EvalRunRecord.id)).where(
                    EvalRunRecord.workspace_id == row.workspace_id,
                    EvalRunRecord.dataset_name == row.dataset_name,
                    EvalRunRecord.experiment_name == row.name,
                )
            ).scalar_one()
        except OperationalError as exc:
            if "workspace_id" not in str(exc) and "experiment_name" not in str(exc):
                raise
            run_count = 0
        return ExperimentResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            dataset_name=row.dataset_name,
            owner=row.owner,
            status=row.status,
            description=row.description,
            baseline_run_id=row.baseline_run_id,
            candidate_run_id=row.candidate_run_id,
            experiment_metadata={str(key): str(value) for key, value in (row.experiment_metadata or {}).items()},
            created_at=row.created_at,
            updated_at=row.updated_at,
            run_count=run_count,
        )

    @staticmethod
    def _list_run_trends(
        db: Session, workspace_id: str, dataset_name: str, experiment_name: str
    ) -> list[ExperimentRunTrend]:
        try:
            rows = db.execute(
                select(EvalRunRecord)
                .where(
                    EvalRunRecord.workspace_id == workspace_id,
                    EvalRunRecord.dataset_name == dataset_name,
                    EvalRunRecord.experiment_name == experiment_name,
                )
                .order_by(EvalRunRecord.created_at.desc())
                .limit(20)
            ).scalars().all()
        except OperationalError as exc:
            if "workspace_id" not in str(exc) and "experiment_name" not in str(exc):
                raise
            return []
        return [
            ExperimentRunTrend(
                run_id=row.id,
                prompt_version=row.prompt_version,
                model_name=row.model_name,
                evaluator_version=row.evaluator_version,
                average_score=row.average_score,
                created_at=row.created_at,
            )
            for row in rows
        ]

    @staticmethod
    def _list_gate_trends(
        db: Session, workspace_id: str, dataset_name: str, experiment_name: str
    ) -> list[ExperimentGateTrend]:
        try:
            rows = db.execute(
                select(ReleaseGateDecisionRecord)
                .where(
                    ReleaseGateDecisionRecord.workspace_id == workspace_id,
                    ReleaseGateDecisionRecord.dataset_name == dataset_name,
                    ReleaseGateDecisionRecord.experiment_name == experiment_name,
                )
                .order_by(ReleaseGateDecisionRecord.created_at.desc())
                .limit(20)
            ).scalars().all()
        except OperationalError as exc:
            if "workspace_id" not in str(exc) and "experiment_name" not in str(exc):
                raise
            return []
        return [
            ExperimentGateTrend(
                gate_id=row.id,
                status=row.status,
                baseline_run_id=row.baseline_run_id,
                candidate_run_id=row.candidate_run_id,
                score_delta=float((row.metrics or {}).get("score_delta", 0.0)),
                failed_case_delta=int((row.metrics or {}).get("failed_case_delta", 0)),
                created_at=row.created_at,
            )
            for row in rows
        ]

    @staticmethod
    def _ensure_experiments_table(db: Session) -> None:
        inspector = inspect(db.bind)
        existing_tables = set(inspector.get_table_names())
        if "experiments" not in existing_tables:
            db.execute(
                text(
                    """
                    CREATE TABLE experiments (
                        id VARCHAR(36) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(100) NOT NULL DEFAULT 'default',
                        name VARCHAR(100) NOT NULL,
                        dataset_name VARCHAR(100) NOT NULL,
                        owner VARCHAR(100) NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'draft',
                        description TEXT NOT NULL DEFAULT '',
                        baseline_run_id VARCHAR(36) NOT NULL DEFAULT '',
                        candidate_run_id VARCHAR(36) NOT NULL DEFAULT '',
                        experiment_metadata JSON NOT NULL DEFAULT '{}',
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            db.execute(text("CREATE INDEX ix_experiments_workspace_id ON experiments (workspace_id)"))
            db.execute(text("CREATE INDEX ix_experiments_name ON experiments (name)"))
            db.execute(text("CREATE INDEX ix_experiments_dataset_name ON experiments (dataset_name)"))
            db.execute(text("CREATE INDEX ix_experiments_status ON experiments (status)"))
            db.execute(
                text(
                    "CREATE UNIQUE INDEX uq_experiment_workspace_name_idx "
                    "ON experiments (workspace_id, name)"
                )
            )
            db.commit()


experiment_service = ExperimentService()
