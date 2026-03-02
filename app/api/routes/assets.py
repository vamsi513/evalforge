from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.assets import (
    DatasetBundle,
    DatasetBundleImport,
    GoldenCaseCreate,
    GoldenCaseResponse,
    PromptTemplateCreate,
    PromptTemplateResponse,
)
from app.services.asset_service import asset_service

router = APIRouter()


@router.get("/prompts", response_model=list[PromptTemplateResponse])
async def list_prompt_templates(
    dataset_name: Optional[str] = Query(default=None), db: Session = Depends(get_db)
) -> list[PromptTemplateResponse]:
    return asset_service.list_prompt_templates(db, dataset_name=dataset_name)


@router.post("/prompts", response_model=PromptTemplateResponse, status_code=201)
async def create_prompt_template(
    payload: PromptTemplateCreate, db: Session = Depends(get_db)
) -> PromptTemplateResponse:
    if asset_service.prompt_template_exists(db, payload.dataset_name, payload.version):
        raise HTTPException(status_code=409, detail="Prompt template version already exists")
    return asset_service.create_prompt_template(db, payload)


@router.get("/golden-cases", response_model=list[GoldenCaseResponse])
async def list_golden_cases(
    dataset_name: Optional[str] = Query(default=None), db: Session = Depends(get_db)
) -> list[GoldenCaseResponse]:
    return asset_service.list_golden_cases(db, dataset_name=dataset_name)


@router.post("/golden-cases", response_model=GoldenCaseResponse, status_code=201)
async def create_golden_case(
    payload: GoldenCaseCreate, db: Session = Depends(get_db)
) -> GoldenCaseResponse:
    return asset_service.create_golden_case(db, payload)


@router.get("/bundles/{dataset_name}", response_model=DatasetBundle)
async def export_dataset_bundle(dataset_name: str, db: Session = Depends(get_db)) -> DatasetBundle:
    bundle = asset_service.export_bundle(db, dataset_name)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return bundle


@router.post("/bundles/import", response_model=DatasetBundle, status_code=201)
async def import_dataset_bundle(
    payload: DatasetBundleImport, db: Session = Depends(get_db)
) -> DatasetBundle:
    if any(prompt.dataset_name != payload.dataset.name for prompt in payload.prompts):
        raise HTTPException(status_code=422, detail="Prompt template dataset names must match bundle dataset")
    if any(case.dataset_name != payload.dataset.name for case in payload.golden_cases):
        raise HTTPException(status_code=422, detail="Golden case dataset names must match bundle dataset")
    return asset_service.import_bundle(db, payload)
