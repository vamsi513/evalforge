import json
from datetime import datetime
from typing import Optional

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import EvalJobRecord, EvalRunRecord
from app.db.session import SessionLocal
from app.engine.evaluator import eval_runner
from app.engine.judge import judge_client
from app.models.assets import StoredEvalRunCreate
from app.models.eval_run import (
    AsyncEvalJobResponse,
    EvalCaseResult,
    EvalRunCreate,
    EvalRunResponse,
    JudgeEvalCreate,
    JudgeEvalResponse,
    PairwiseEvalCreate,
    PairwiseEvalResponse,
)
from app.services.asset_service import asset_service


class EvalService:
    def list_runs(self, db: Session, workspace_id: str = "default") -> list[EvalRunResponse]:
        try:
            rows = db.execute(
                select(EvalRunRecord)
                .where(EvalRunRecord.workspace_id == workspace_id)
                .order_by(EvalRunRecord.created_at.desc())
            ).scalars().all()
            return [self._to_response(row) for row in rows]
        except OperationalError as exc:
            if "experiment_name" not in str(exc) and "workspace_id" not in str(exc):
                raise
            return self._list_legacy_runs(db, workspace_id=workspace_id)

    def get_run_by_id(self, db: Session, run_id: str, workspace_id: str = "default") -> Optional[EvalRunResponse]:
        try:
            row = db.execute(
                select(EvalRunRecord).where(
                    EvalRunRecord.id == run_id,
                    EvalRunRecord.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_response(row)
        except OperationalError as exc:
            if "experiment_name" not in str(exc) and "workspace_id" not in str(exc):
                raise
            return self._get_legacy_run_by_id(db, run_id, workspace_id=workspace_id)

    def create_run(self, db: Session, payload: EvalRunCreate, workspace_id: str = "default") -> EvalRunResponse:
        results, average_score = eval_runner.run(payload)
        return self._persist_eval_run(
            db=db,
            workspace_id=workspace_id,
            dataset_name=payload.dataset_name,
            experiment_name=payload.experiment_name,
            prompt_version=payload.prompt_version,
            model_name=payload.model_name,
            evaluator_version=payload.evaluator_version,
            average_score=average_score,
            run_metadata=payload.run_metadata,
            results=[result.model_dump() for result in results],
        )

    def list_jobs(self, db: Session, workspace_id: str = "default") -> list[AsyncEvalJobResponse]:
        try:
            rows = db.execute(
                select(EvalJobRecord)
                .where(EvalJobRecord.workspace_id == workspace_id)
                .order_by(EvalJobRecord.created_at.desc())
            ).scalars().all()
        except OperationalError as exc:
            if "workspace_id" not in str(exc):
                raise
            self._ensure_eval_jobs_workspace_column(db)
            rows = db.execute(
                select(EvalJobRecord)
                .where(EvalJobRecord.workspace_id == workspace_id)
                .order_by(EvalJobRecord.created_at.desc())
            ).scalars().all()
        return [self._to_job_response(row) for row in rows]

    def get_job(self, db: Session, job_id: str, workspace_id: str = "default") -> Optional[AsyncEvalJobResponse]:
        try:
            row = db.execute(
                select(EvalJobRecord).where(
                    EvalJobRecord.id == job_id,
                    EvalJobRecord.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()
        except OperationalError as exc:
            if "workspace_id" not in str(exc):
                raise
            self._ensure_eval_jobs_workspace_column(db)
            row = db.execute(
                select(EvalJobRecord).where(
                    EvalJobRecord.id == job_id,
                    EvalJobRecord.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()
        if row is None:
            return None
        return self._to_job_response(row)

    def enqueue_run(
        self, db: Session, payload: EvalRunCreate, workspace_id: str = "default"
    ) -> AsyncEvalJobResponse:
        row = EvalJobRecord(
            job_type="eval_run",
            status="queued",
            workspace_id=workspace_id,
            dataset_name=payload.dataset_name,
            payload=payload.model_dump(),
            result={},
            error_message="",
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except OperationalError as exc:
            db.rollback()
            if "workspace_id" not in str(exc):
                raise
            self._ensure_eval_jobs_workspace_column(db)
            row = EvalJobRecord(
                job_type="eval_run",
                status="queued",
                workspace_id=workspace_id,
                dataset_name=payload.dataset_name,
                payload=payload.model_dump(),
                result={},
                error_message="",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._to_job_response(row)

    def process_run_job(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            row = db.execute(select(EvalJobRecord).where(EvalJobRecord.id == job_id)).scalar_one_or_none()
            if row is None:
                return
            row.status = "running"
            row.updated_at = datetime.utcnow()
            db.commit()

            payload = EvalRunCreate(**row.payload)
            run_response = self.create_run(db, payload, workspace_id=row.workspace_id)

            row.result = run_response.model_dump(mode="json")
            row.status = "completed"
            row.error_message = ""
            row.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed_row = db.execute(
                select(EvalJobRecord).where(EvalJobRecord.id == job_id)
            ).scalar_one_or_none()
            if failed_row is not None:
                failed_row.status = "failed"
                failed_row.error_message = str(exc)
                failed_row.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def compare_runs(self, db: Session, payload: PairwiseEvalCreate) -> PairwiseEvalResponse:
        return eval_runner.compare(payload)

    def judge_run(self, db: Session, payload: JudgeEvalCreate, workspace_id: str = "default") -> JudgeEvalResponse:
        response = judge_client.evaluate(
            dataset_name=payload.dataset_name,
            prompt_version=payload.prompt_version,
            model_name=payload.model_name,
            samples=payload.samples,
        )
        self._persist_eval_run(
            db=db,
            workspace_id=workspace_id,
            dataset_name=response.dataset_name,
            experiment_name="judge-evals",
            prompt_version=response.prompt_version,
            model_name=response.model_name,
            evaluator_version=f"judge:{response.judge_provider}:{response.judge_model}",
            average_score=response.average_score,
            run_metadata={
                "judge_provider": response.judge_provider,
                "judge_model": response.judge_model,
            },
            results=[result.model_dump() for result in response.results],
        )
        return response

    def create_run_from_stored_cases(
        self, db: Session, payload: StoredEvalRunCreate, workspace_id: str = "default"
    ) -> EvalRunResponse:
        stored_cases = asset_service.get_golden_cases(db, payload.dataset_name, workspace_id=workspace_id)
        if not stored_cases:
            raise ValueError("No golden cases found for dataset")
        if len(stored_cases) != len(payload.candidate_outputs):
            raise ValueError("candidate_outputs length must match stored golden case count")

        samples = [
            {
                "prompt": case.input_prompt,
                "expected_keyword": case.expected_keyword,
                "candidate_output": candidate_output,
                "scenario": case.scenario,
                "slice_name": case.slice_name,
                "severity": case.severity,
                "required_json_fields": case.required_json_fields,
                "reference_answer": case.reference_answer,
                "rubric": case.rubric,
            }
            for case, candidate_output in zip(stored_cases, payload.candidate_outputs)
        ]
        return self.create_run(
            db,
            EvalRunCreate(
                dataset_name=payload.dataset_name,
                experiment_name="stored-case-runs",
                prompt_version=payload.prompt_version,
                model_name=payload.model_name,
                samples=samples,
            ),
            workspace_id=workspace_id,
        )

    @staticmethod
    def _to_response(row: EvalRunRecord) -> EvalRunResponse:
        return EvalRunResponse(
            id=row.id,
            dataset_name=row.dataset_name,
            workspace_id=getattr(row, "workspace_id", "default"),
            experiment_name=row.experiment_name,
            prompt_version=row.prompt_version,
            model_name=row.model_name,
            evaluator_version=row.evaluator_version,
            average_score=row.average_score,
            run_metadata={str(key): str(value) for key, value in (row.run_metadata or {}).items()},
            created_at=row.created_at,
            results=[EvalCaseResult(**EvalService._normalize_result(result)) for result in row.results],
        )

    @staticmethod
    def _persist_eval_run(
        *,
        db: Session,
        workspace_id: str,
        dataset_name: str,
        experiment_name: str,
        prompt_version: str,
        model_name: str,
        evaluator_version: str,
        average_score: float,
        run_metadata: dict,
        results: list[dict],
    ) -> EvalRunResponse:
        row = EvalRunRecord(
            workspace_id=workspace_id,
            dataset_name=dataset_name,
            experiment_name=experiment_name,
            prompt_version=prompt_version,
            model_name=model_name,
            evaluator_version=evaluator_version,
            average_score=average_score,
            run_metadata=run_metadata,
            results=results,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except OperationalError as exc:
            db.rollback()
            if (
                "experiment_name" not in str(exc)
                and "evaluator_version" not in str(exc)
                and "run_metadata" not in str(exc)
                and "workspace_id" not in str(exc)
            ):
                raise
            EvalService._ensure_eval_runs_modern_columns(db)
            row = EvalRunRecord(
                workspace_id=workspace_id,
                dataset_name=dataset_name,
                experiment_name=experiment_name,
                prompt_version=prompt_version,
                model_name=model_name,
                evaluator_version=evaluator_version,
                average_score=average_score,
                run_metadata=run_metadata,
                results=results,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return EvalService._to_response(row)

    @staticmethod
    def _to_job_response(row: EvalJobRecord) -> AsyncEvalJobResponse:
        result = row.result or {}
        parsed_result = EvalRunResponse(**result) if result else None
        return AsyncEvalJobResponse(
            id=row.id,
            job_type=row.job_type,
            status=row.status,
            dataset_name=row.dataset_name,
            workspace_id=getattr(row, "workspace_id", "default"),
            created_at=row.created_at,
            updated_at=row.updated_at,
            error_message=row.error_message,
            result=parsed_result,
        )

    @staticmethod
    def _normalize_result(result: dict) -> dict:
        normalized = dict(result)
        normalized.setdefault("reference_answer", None)
        normalized.setdefault("scenario", "general")
        normalized.setdefault("slice_name", "default")
        normalized.setdefault("severity", "medium")
        normalized.setdefault("required_json_fields", [])
        normalized.setdefault("rubric", [])
        normalized.setdefault("passed", normalized.get("score", 0.0) >= 0.65)
        normalized.setdefault("matched_terms", [])
        normalized.setdefault("missing_terms", [])
        normalized.setdefault("unsupported_terms", [])
        normalized.setdefault("criterion_scores", {})
        normalized.setdefault("structured_output_valid", False)
        normalized.setdefault("structured_output_error", "")
        normalized.setdefault("groundedness_score", 1.0)
        normalized.setdefault("groundedness_feedback", "")
        normalized.setdefault("feedback", "Loaded from legacy eval record.")
        return normalized

    @staticmethod
    def _ensure_eval_runs_modern_columns(db: Session) -> None:
        inspector = inspect(db.bind)
        existing_columns = {column["name"] for column in inspector.get_columns("eval_runs")}
        if "workspace_id" not in existing_columns:
            db.execute(text("ALTER TABLE eval_runs ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'"))
        if "experiment_name" not in existing_columns:
            db.execute(text("ALTER TABLE eval_runs ADD COLUMN experiment_name VARCHAR(100) NOT NULL DEFAULT ''"))
        if "evaluator_version" not in existing_columns:
            db.execute(
                text("ALTER TABLE eval_runs ADD COLUMN evaluator_version VARCHAR(50) NOT NULL DEFAULT 'heuristic-v1'")
            )
        if "run_metadata" not in existing_columns:
            db.execute(text("ALTER TABLE eval_runs ADD COLUMN run_metadata JSON NOT NULL DEFAULT '{}'"))
        existing_indexes = {index["name"] for index in inspector.get_indexes("eval_runs")}
        if "ix_eval_runs_workspace_id" not in existing_indexes:
            db.execute(text("CREATE INDEX ix_eval_runs_workspace_id ON eval_runs (workspace_id)"))
        if "ix_eval_runs_experiment_name" not in existing_indexes:
            db.execute(text("CREATE INDEX ix_eval_runs_experiment_name ON eval_runs (experiment_name)"))
        db.commit()

    @staticmethod
    def _list_legacy_runs(db: Session, workspace_id: str = "default") -> list[EvalRunResponse]:
        if workspace_id != "default":
            return []
        rows = db.execute(
            text(
                """
                SELECT id, dataset_name, prompt_version, model_name, average_score, results, created_at
                FROM eval_runs
                ORDER BY created_at DESC
                """
            )
        ).mappings()
        return [EvalService._legacy_row_to_response(row) for row in rows]

    @staticmethod
    def _get_legacy_run_by_id(
        db: Session, run_id: str, workspace_id: str = "default"
    ) -> Optional[EvalRunResponse]:
        if workspace_id != "default":
            return None
        row = db.execute(
            text(
                """
                SELECT id, dataset_name, prompt_version, model_name, average_score, results, created_at
                FROM eval_runs
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().first()
        if row is None:
            return None
        return EvalService._legacy_row_to_response(row)

    @staticmethod
    def _legacy_row_to_response(row: dict) -> EvalRunResponse:
        results = row["results"]
        if isinstance(results, str):
            results = json.loads(results)
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return EvalRunResponse(
            id=row["id"],
            dataset_name=row["dataset_name"],
            workspace_id="default",
            experiment_name="",
            prompt_version=row["prompt_version"],
            model_name=row["model_name"],
            evaluator_version="heuristic-v1",
            average_score=row["average_score"],
            run_metadata={},
            created_at=created_at,
            results=[EvalCaseResult(**EvalService._normalize_result(result)) for result in results],
        )

    @staticmethod
    def _ensure_eval_jobs_workspace_column(db: Session) -> None:
        inspector = inspect(db.bind)
        existing_columns = {column["name"] for column in inspector.get_columns("eval_jobs")}
        if "workspace_id" not in existing_columns:
            db.execute(
                text("ALTER TABLE eval_jobs ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'")
            )
        existing_indexes = {index["name"] for index in inspector.get_indexes("eval_jobs")}
        if "ix_eval_jobs_workspace_id" not in existing_indexes:
            db.execute(text("CREATE INDEX ix_eval_jobs_workspace_id ON eval_jobs (workspace_id)"))
        db.commit()


eval_service = EvalService()
