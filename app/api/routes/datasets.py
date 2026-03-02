from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.dataset import DatasetCreate, DatasetResponse
from app.services.dataset_service import dataset_service

router = APIRouter()


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(db: Session = Depends(get_db)) -> list[DatasetResponse]:
    return dataset_service.list_datasets(db)


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db)) -> DatasetResponse:
    if dataset_service.exists(db, payload.name):
        raise HTTPException(status_code=409, detail="Dataset already exists")
    return dataset_service.create_dataset(db, payload)
