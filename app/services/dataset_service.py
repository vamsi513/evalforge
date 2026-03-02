from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DatasetRecord
from app.models.dataset import DatasetCreate, DatasetResponse


class DatasetService:
    def list_datasets(self, db: Session) -> list[DatasetResponse]:
        rows = db.execute(select(DatasetRecord).order_by(DatasetRecord.created_at.desc())).scalars().all()
        return [self._to_response(row) for row in rows]

    def create_dataset(self, db: Session, payload: DatasetCreate) -> DatasetResponse:
        row = DatasetRecord(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._to_response(row)

    def exists(self, db: Session, name: str) -> bool:
        query = select(DatasetRecord.id).where(DatasetRecord.name == name)
        return db.execute(query).first() is not None

    @staticmethod
    def _to_response(row: DatasetRecord) -> DatasetResponse:
        return DatasetResponse(
            id=row.id,
            name=row.name,
            description=row.description,
            owner=row.owner,
            created_at=row.created_at,
        )


dataset_service = DatasetService()
