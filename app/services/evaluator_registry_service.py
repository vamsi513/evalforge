from datetime import datetime

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import EvaluatorDefinitionRecord
from app.engine.evaluator_registry import build_default_registry
from app.models.evaluator_definition import EvaluatorDefinitionCreate, EvaluatorDefinitionResponse


class EvaluatorRegistryService:
    DEFAULT_VERSION = "heuristic-v1"

    def list_definitions(self, db: Session) -> list[EvaluatorDefinitionResponse]:
        try:
            self._bootstrap_defaults(db)
            rows = db.execute(
                select(EvaluatorDefinitionRecord).order_by(
                    EvaluatorDefinitionRecord.kind.asc(),
                    EvaluatorDefinitionRecord.name.asc(),
                    EvaluatorDefinitionRecord.version.desc(),
                )
            ).scalars().all()
        except OperationalError as exc:
            if "evaluator_definitions" not in str(exc):
                raise
            self._ensure_table(db)
            self._bootstrap_defaults(db)
            rows = db.execute(
                select(EvaluatorDefinitionRecord).order_by(
                    EvaluatorDefinitionRecord.kind.asc(),
                    EvaluatorDefinitionRecord.name.asc(),
                    EvaluatorDefinitionRecord.version.desc(),
                )
            ).scalars().all()
        return [self._to_response(row) for row in rows]

    def create_definition(self, db: Session, payload: EvaluatorDefinitionCreate) -> EvaluatorDefinitionResponse:
        row = EvaluatorDefinitionRecord(**payload.model_dump())
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except OperationalError as exc:
            db.rollback()
            if "evaluator_definitions" not in str(exc):
                raise
            self._ensure_table(db)
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._to_response(row)

    def exists(self, db: Session, name: str, version: str) -> bool:
        query = select(EvaluatorDefinitionRecord.id).where(
            EvaluatorDefinitionRecord.name == name,
            EvaluatorDefinitionRecord.version == version,
        )
        try:
            return db.execute(query).first() is not None
        except OperationalError as exc:
            if "evaluator_definitions" not in str(exc):
                raise
            self._ensure_table(db)
            return db.execute(query).first() is not None

    def _bootstrap_defaults(self, db: Session) -> None:
        registry = build_default_registry()
        now = datetime.utcnow()
        for definition in registry.definitions():
            exists = db.execute(
                select(EvaluatorDefinitionRecord.id).where(
                    EvaluatorDefinitionRecord.name == definition["name"],
                    EvaluatorDefinitionRecord.version == self.DEFAULT_VERSION,
                )
            ).first()
            if exists:
                continue
            db.add(
                EvaluatorDefinitionRecord(
                    name=definition["name"],
                    version=self.DEFAULT_VERSION,
                    kind=definition["kind"],
                    status="active",
                    description=f"Built-in {definition['kind']} evaluator used by the default scoring registry.",
                    config={"registry_version": self.DEFAULT_VERSION},
                    created_at=now,
                    updated_at=now,
                )
            )
        db.commit()

    @staticmethod
    def _to_response(row: EvaluatorDefinitionRecord) -> EvaluatorDefinitionResponse:
        return EvaluatorDefinitionResponse(
            id=row.id,
            name=row.name,
            version=row.version,
            kind=row.kind,
            status=row.status,
            description=row.description,
            config={str(key): str(value) for key, value in (row.config or {}).items()},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _ensure_table(db: Session) -> None:
        inspector = inspect(db.bind)
        if "evaluator_definitions" in inspector.get_table_names():
            return
        db.execute(
            text(
                """
                CREATE TABLE evaluator_definitions (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    kind VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    description TEXT NOT NULL DEFAULT '',
                    config JSON NOT NULL DEFAULT '{}',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        db.execute(text("CREATE INDEX ix_evaluator_definitions_name ON evaluator_definitions (name)"))
        db.execute(text("CREATE INDEX ix_evaluator_definitions_version ON evaluator_definitions (version)"))
        db.execute(text("CREATE INDEX ix_evaluator_definitions_kind ON evaluator_definitions (kind)"))
        db.execute(text("CREATE INDEX ix_evaluator_definitions_status ON evaluator_definitions (status)"))
        db.execute(
            text(
                "CREATE UNIQUE INDEX uq_evaluator_name_version_idx "
                "ON evaluator_definitions (name, version)"
            )
        )
        db.commit()


evaluator_registry_service = EvaluatorRegistryService()

