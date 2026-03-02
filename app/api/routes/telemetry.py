from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.telemetry import TelemetrySummary
from app.services.telemetry_service import telemetry_service

router = APIRouter()


@router.get("/summary", response_model=TelemetrySummary)
async def telemetry_summary(db: Session = Depends(get_db)) -> TelemetrySummary:
    return telemetry_service.summary(db)
