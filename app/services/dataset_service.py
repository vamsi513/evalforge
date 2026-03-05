from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import DatasetRecord
from app.models.dataset import DatasetCreate, DatasetResponse


class DatasetService:
    def list_datasets(self, db: Session, workspace_id: str) -> list[DatasetResponse]:
        try:
            rows = db.execute(
                select(DatasetRecord)
                .where(DatasetRecord.workspace_id == workspace_id)
                .order_by(DatasetRecord.created_at.desc())
            ).scalars().all()
        except OperationalError as exc:
            if "workspace_id" not in str(exc):
                raise
            self._ensure_workspace_column(db)
            rows = db.execute(
                select(DatasetRecord)
                .where(DatasetRecord.workspace_id == workspace_id)
                .order_by(DatasetRecord.created_at.desc())
            ).scalars().all()
        return [self._to_response(row) for row in rows]

    def create_dataset(self, db: Session, payload: DatasetCreate, workspace_id: str) -> DatasetResponse:
        row = DatasetRecord(workspace_id=workspace_id, **payload.model_dump())
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except OperationalError as exc:
            db.rollback()
            if "workspace_id" not in str(exc):
                raise
            self._ensure_workspace_column(db)
            row = DatasetRecord(workspace_id=workspace_id, **payload.model_dump())
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._to_response(row)

    def exists(self, db: Session, name: str, workspace_id: str) -> bool:
        query = select(DatasetRecord.id).where(
            DatasetRecord.name == name,
            DatasetRecord.workspace_id == workspace_id,
        )
        try:
            return db.execute(query).first() is not None
        except OperationalError as exc:
            if "workspace_id" not in str(exc):
                raise
            self._ensure_workspace_column(db)
            return db.execute(query).first() is not None

    @staticmethod
    def _to_response(row: DatasetRecord) -> DatasetResponse:
        return DatasetResponse(
            id=row.id,
            name=row.name,
            description=row.description,
            owner=row.owner,
            workspace_id=getattr(row, "workspace_id", "default"),
            created_at=row.created_at,
        )

    @staticmethod
    def _ensure_workspace_column(db: Session) -> None:
        inspector = inspect(db.bind)
        existing_columns = {column["name"] for column in inspector.get_columns("datasets")}
        if "workspace_id" not in existing_columns:
            db.execute(
                text("ALTER TABLE datasets ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'")
            )
        existing_indexes = {index["name"] for index in inspector.get_indexes("datasets")}
        if "ix_datasets_workspace_id" not in existing_indexes:
            db.execute(text("CREATE INDEX ix_datasets_workspace_id ON datasets (workspace_id)"))
        db.commit()


dataset_service = DatasetService()
