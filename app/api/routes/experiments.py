from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_workspace_id
from app.db.session import get_db
from app.models.experiment import ExperimentCreate, ExperimentReport, ExperimentResponse
from app.services.experiment_service import experiment_service

router = APIRouter()


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    workspace_id: str = Depends(get_workspace_id), db: Session = Depends(get_db)
) -> list[ExperimentResponse]:
    return experiment_service.list_experiments(db, workspace_id)


@router.post("", response_model=ExperimentResponse, status_code=201)
async def create_experiment(
    payload: ExperimentCreate,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ExperimentResponse:
    if experiment_service.exists(db, payload.name, workspace_id):
        raise HTTPException(status_code=409, detail="Experiment already exists")
    return experiment_service.create_experiment(db, payload, workspace_id)


@router.get("/{experiment_name}/report", response_model=ExperimentReport)
async def get_experiment_report(
    experiment_name: str,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ExperimentReport:
    report = experiment_service.get_experiment_report(db, experiment_name, workspace_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return report
