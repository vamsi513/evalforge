from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.evaluator_definition import EvaluatorDefinitionCreate, EvaluatorDefinitionResponse
from app.services.evaluator_registry_service import evaluator_registry_service

router = APIRouter()


@router.get("", response_model=list[EvaluatorDefinitionResponse])
async def list_evaluators(db: Session = Depends(get_db)) -> list[EvaluatorDefinitionResponse]:
    return evaluator_registry_service.list_definitions(db)


@router.post("", response_model=EvaluatorDefinitionResponse, status_code=201)
async def create_evaluator(
    payload: EvaluatorDefinitionCreate,
    db: Session = Depends(get_db),
) -> EvaluatorDefinitionResponse:
    if evaluator_registry_service.exists(db, payload.name, payload.version):
        raise HTTPException(status_code=409, detail="Evaluator definition already exists")
    return evaluator_registry_service.create_definition(db, payload)

