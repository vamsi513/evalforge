from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_workspace_id, require_editor_role
from app.db.session import get_db
from app.models.experiment import (
    ExperimentCreate,
    ExperimentPromotionEvent,
    ExperimentPromoteRequest,
    ExperimentPromoteResponse,
    ExperimentReport,
    ExperimentResponse,
)
from app.services.experiment_service import experiment_service

router = APIRouter()


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    workspace_id: str = Depends(get_workspace_id), db: Session = Depends(get_db)
) -> list[ExperimentResponse]:
    return experiment_service.list_experiments(db, workspace_id)


@router.post("", response_model=ExperimentResponse, status_code=201, dependencies=[Depends(require_editor_role)])
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


@router.post(
    "/{experiment_name}/promote",
    response_model=ExperimentPromoteResponse,
    dependencies=[Depends(require_editor_role)],
)
async def promote_experiment_candidate(
    experiment_name: str,
    payload: ExperimentPromoteRequest,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ExperimentPromoteResponse:
    try:
        return experiment_service.promote_candidate(
            db=db,
            name=experiment_name,
            payload=payload,
            workspace_id=workspace_id,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "Experiment not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc


@router.get("/{experiment_name}/release-history", response_model=list[ExperimentPromotionEvent])
async def list_experiment_release_history(
    experiment_name: str,
    limit: int = 50,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> list[ExperimentPromotionEvent]:
    try:
        return experiment_service.list_promotion_events(
            db=db,
            name=experiment_name,
            workspace_id=workspace_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{experiment_name}/release-history/export.csv")
async def export_experiment_release_history_csv(
    experiment_name: str,
    limit: int = 200,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> Response:
    try:
        csv_payload = experiment_service.export_promotion_events_csv(
            db=db,
            name=experiment_name,
            workspace_id=workspace_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    filename = f"{experiment_name}_release_history.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=csv_payload, media_type="text/csv", headers=headers)
