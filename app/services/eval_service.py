from datetime import datetime
from typing import Optional

from sqlalchemy import select
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
    def list_runs(self, db: Session) -> list[EvalRunResponse]:
        rows = db.execute(select(EvalRunRecord).order_by(EvalRunRecord.created_at.desc())).scalars().all()
        return [self._to_response(row) for row in rows]

    def create_run(self, db: Session, payload: EvalRunCreate) -> EvalRunResponse:
        results, average_score = eval_runner.run(payload)
        row = EvalRunRecord(
            dataset_name=payload.dataset_name,
            prompt_version=payload.prompt_version,
            model_name=payload.model_name,
            average_score=average_score,
            results=[result.model_dump() for result in results],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._to_response(row)

    def list_jobs(self, db: Session) -> list[AsyncEvalJobResponse]:
        rows = db.execute(select(EvalJobRecord).order_by(EvalJobRecord.created_at.desc())).scalars().all()
        return [self._to_job_response(row) for row in rows]

    def get_job(self, db: Session, job_id: str) -> Optional[AsyncEvalJobResponse]:
        row = db.execute(select(EvalJobRecord).where(EvalJobRecord.id == job_id)).scalar_one_or_none()
        if row is None:
            return None
        return self._to_job_response(row)

    def enqueue_run(self, db: Session, payload: EvalRunCreate) -> AsyncEvalJobResponse:
        row = EvalJobRecord(
            job_type="eval_run",
            status="queued",
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
            run_response = self.create_run(db, payload)

            row.result = run_response.model_dump(mode="json")
            row.status = "completed"
            row.error_message = ""
            row.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:  # noqa: BLE001
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
        dataset_exists = db.execute(
            select(EvalRunRecord.id).where(EvalRunRecord.dataset_name == payload.dataset_name)
        ).first()
        if dataset_exists is None:
            return eval_runner.compare(payload)
        return eval_runner.compare(payload)

    def judge_run(self, db: Session, payload: JudgeEvalCreate) -> JudgeEvalResponse:
        _ = db
        return judge_client.evaluate(
            dataset_name=payload.dataset_name,
            prompt_version=payload.prompt_version,
            model_name=payload.model_name,
            samples=payload.samples,
        )

    def create_run_from_stored_cases(self, db: Session, payload: StoredEvalRunCreate) -> EvalRunResponse:
        stored_cases = asset_service.get_golden_cases(db, payload.dataset_name)
        if not stored_cases:
            raise ValueError("No golden cases found for dataset")
        if len(stored_cases) != len(payload.candidate_outputs):
            raise ValueError("candidate_outputs length must match stored golden case count")

        samples = [
            {
                "prompt": case.input_prompt,
                "expected_keyword": case.expected_keyword,
                "candidate_output": candidate_output,
                "reference_answer": case.reference_answer,
                "rubric": case.rubric,
            }
            for case, candidate_output in zip(stored_cases, payload.candidate_outputs)
        ]
        return self.create_run(
            db,
            EvalRunCreate(
                dataset_name=payload.dataset_name,
                prompt_version=payload.prompt_version,
                model_name=payload.model_name,
                samples=samples,
            ),
        )

    @staticmethod
    def _to_response(row: EvalRunRecord) -> EvalRunResponse:
        return EvalRunResponse(
            id=row.id,
            dataset_name=row.dataset_name,
            prompt_version=row.prompt_version,
            model_name=row.model_name,
            average_score=row.average_score,
            created_at=row.created_at,
            results=[EvalCaseResult(**EvalService._normalize_result(result)) for result in row.results],
        )

    @staticmethod
    def _to_job_response(row: EvalJobRecord) -> AsyncEvalJobResponse:
        result = row.result or {}
        parsed_result = EvalRunResponse(**result) if result else None
        return AsyncEvalJobResponse(
            id=row.id,
            job_type=row.job_type,
            status=row.status,
            dataset_name=row.dataset_name,
            created_at=row.created_at,
            updated_at=row.updated_at,
            error_message=row.error_message,
            result=parsed_result,
        )

    @staticmethod
    def _normalize_result(result: dict) -> dict:
        normalized = dict(result)
        normalized.setdefault("reference_answer", None)
        normalized.setdefault("rubric", [])
        normalized.setdefault("passed", normalized.get("score", 0.0) >= 0.65)
        normalized.setdefault("matched_terms", [])
        normalized.setdefault("missing_terms", [])
        normalized.setdefault("criterion_scores", {})
        normalized.setdefault("feedback", "Loaded from legacy eval record.")
        return normalized


eval_service = EvalService()
