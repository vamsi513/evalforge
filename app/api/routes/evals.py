from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.assets import StoredEvalRunCreate
from app.models.eval_run import (
    AsyncEvalJobResponse,
    EvalRunCreate,
    EvalRunResponse,
    JudgeEvalCreate,
    JudgeEvalResponse,
    PairwiseEvalCreate,
    PairwiseEvalResponse,
)
from app.services.eval_service import eval_service

router = APIRouter()


@router.get("", response_model=list[EvalRunResponse])
async def list_eval_runs(db: Session = Depends(get_db)) -> list[EvalRunResponse]:
    return eval_service.list_runs(db)


@router.get("/jobs", response_model=list[AsyncEvalJobResponse])
async def list_eval_jobs(db: Session = Depends(get_db)) -> list[AsyncEvalJobResponse]:
    return eval_service.list_jobs(db)


@router.get("/jobs/{job_id}", response_model=AsyncEvalJobResponse)
async def get_eval_job(job_id: str, db: Session = Depends(get_db)) -> AsyncEvalJobResponse:
    job = eval_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=EvalRunResponse, status_code=201)
async def create_eval_run(payload: EvalRunCreate, db: Session = Depends(get_db)) -> EvalRunResponse:
    return eval_service.create_run(db, payload)


@router.post("/async", response_model=AsyncEvalJobResponse, status_code=202)
async def create_eval_run_async(
    payload: EvalRunCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> AsyncEvalJobResponse:
    job = eval_service.enqueue_run(db, payload)
    background_tasks.add_task(eval_service.process_run_job, job.id)
    return job


@router.post("/stored", response_model=EvalRunResponse, status_code=201)
async def create_eval_run_from_stored_cases(
    payload: StoredEvalRunCreate, db: Session = Depends(get_db)
) -> EvalRunResponse:
    try:
        return eval_service.create_run_from_stored_cases(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/judge", response_model=JudgeEvalResponse, status_code=201)
async def judge_eval_run(payload: JudgeEvalCreate, db: Session = Depends(get_db)) -> JudgeEvalResponse:
    return eval_service.judge_run(db, payload)


@router.post("/compare", response_model=PairwiseEvalResponse, status_code=201)
async def compare_eval_run(
    payload: PairwiseEvalCreate, db: Session = Depends(get_db)
) -> PairwiseEvalResponse:
    return eval_service.compare_runs(db, payload)
