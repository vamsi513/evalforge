from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_workspace_id, require_editor_role
from app.db.session import get_db
from app.models.dataset import DatasetCreate, DatasetResponse
from app.services.dataset_service import dataset_service

router = APIRouter()


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    workspace_id: str = Depends(get_workspace_id), db: Session = Depends(get_db)
) -> list[DatasetResponse]:
    return dataset_service.list_datasets(db, workspace_id)


@router.post("", response_model=DatasetResponse, status_code=201, dependencies=[Depends(require_editor_role)])
async def create_dataset(
    payload: DatasetCreate,
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> DatasetResponse:
    if dataset_service.exists(db, payload.name, workspace_id):
        raise HTTPException(status_code=409, detail="Dataset already exists")
    return dataset_service.create_dataset(db, payload, workspace_id)
