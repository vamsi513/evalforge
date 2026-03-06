from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_workspace_id, require_admin_role
from app.db.session import get_db
from app.models.model_routing import (
    ModelRoutingPolicyCreate,
    ModelRoutingPolicyResponse,
    ModelRoutingResolutionResponse,
)
from app.services.model_routing_service import model_routing_service

router = APIRouter()


@router.get("", response_model=list[ModelRoutingPolicyResponse])
async def list_model_routing_policies(
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> list[ModelRoutingPolicyResponse]:
    return model_routing_service.list_policies(db, workspace_id)


@router.post(
    "",
    response_model=ModelRoutingPolicyResponse,
    status_code=201,
    dependencies=[Depends(require_admin_role)],
)
async def create_model_routing_policy(
    payload: ModelRoutingPolicyCreate,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ModelRoutingPolicyResponse:
    if model_routing_service.exists(db, workspace_id, payload.use_case, payload.version):
        raise HTTPException(status_code=409, detail="Routing policy already exists")
    return model_routing_service.create_policy(db, payload, workspace_id)


@router.get("/resolve", response_model=ModelRoutingResolutionResponse)
async def resolve_model_route(
    use_case: str,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> ModelRoutingResolutionResponse:
    return model_routing_service.resolve_use_case(db, workspace_id, use_case)
