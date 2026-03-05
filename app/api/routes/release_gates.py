from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_workspace_id
from app.db.session import get_db
from app.models.eval_run import (
    ReleaseGateCiDecisionResponse,
    ReleaseGateCreate,
    ReleaseGateResponse,
    ReleaseGateSummaryResponse,
)
from app.services.release_gate_service import release_gate_service

router = APIRouter()


@router.get("", response_model=list[ReleaseGateResponse])
async def list_release_gates(
    workspace_id: str = Depends(get_workspace_id), db: Session = Depends(get_db)
) -> list[ReleaseGateResponse]:
    return release_gate_service.list_decisions(db, workspace_id=workspace_id)


@router.get("/summary", response_model=ReleaseGateSummaryResponse)
async def get_release_gate_summary(
    dataset_name: str,
    experiment_name: str = "",
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ReleaseGateSummaryResponse:
    return release_gate_service.get_latest_summary(
        db=db,
        dataset_name=dataset_name,
        workspace_id=workspace_id,
        experiment_name=experiment_name,
    )


@router.get("/ci-decision", response_model=ReleaseGateCiDecisionResponse)
async def get_release_gate_ci_decision(
    dataset_name: str,
    experiment_name: str = "",
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ReleaseGateCiDecisionResponse:
    return release_gate_service.get_ci_decision(
        db=db,
        dataset_name=dataset_name,
        workspace_id=workspace_id,
        experiment_name=experiment_name,
    )


@router.post("", response_model=ReleaseGateResponse, status_code=201)
async def create_release_gate(
    payload: ReleaseGateCreate,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ReleaseGateResponse:
    try:
        return release_gate_service.create_decision(db, payload, workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
