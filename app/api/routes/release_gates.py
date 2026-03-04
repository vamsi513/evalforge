from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.eval_run import ReleaseGateCreate, ReleaseGateResponse
from app.services.release_gate_service import release_gate_service

router = APIRouter()


@router.get("", response_model=list[ReleaseGateResponse])
async def list_release_gates(db: Session = Depends(get_db)) -> list[ReleaseGateResponse]:
    return release_gate_service.list_decisions(db)


@router.post("", response_model=ReleaseGateResponse, status_code=201)
async def create_release_gate(
    payload: ReleaseGateCreate, db: Session = Depends(get_db)
) -> ReleaseGateResponse:
    try:
        return release_gate_service.create_decision(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
