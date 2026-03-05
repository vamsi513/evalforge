from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import ModelRoutingPolicyRecord
from app.models.model_routing import (
    ModelRoutingPolicyCreate,
    ModelRoutingPolicyResponse,
    ModelRoutingResolutionResponse,
)


class ModelRoutingService:
    def list_policies(self, db: Session, workspace_id: str) -> list[ModelRoutingPolicyResponse]:
        try:
            rows = db.execute(
                select(ModelRoutingPolicyRecord)
                .where(ModelRoutingPolicyRecord.workspace_id == workspace_id)
                .order_by(
                    ModelRoutingPolicyRecord.use_case.asc(),
                    ModelRoutingPolicyRecord.version.desc(),
                    ModelRoutingPolicyRecord.updated_at.desc(),
                )
            ).scalars().all()
        except OperationalError as exc:
            if "model_routing_policies" not in str(exc):
                raise
            self._ensure_table(db)
            rows = db.execute(
                select(ModelRoutingPolicyRecord)
                .where(ModelRoutingPolicyRecord.workspace_id == workspace_id)
                .order_by(
                    ModelRoutingPolicyRecord.use_case.asc(),
                    ModelRoutingPolicyRecord.version.desc(),
                    ModelRoutingPolicyRecord.updated_at.desc(),
                )
            ).scalars().all()
        return [self._to_response(row) for row in rows]

    def create_policy(
        self, db: Session, payload: ModelRoutingPolicyCreate, workspace_id: str
    ) -> ModelRoutingPolicyResponse:
        row = ModelRoutingPolicyRecord(workspace_id=workspace_id, **payload.model_dump())
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except OperationalError as exc:
            db.rollback()
            if "model_routing_policies" not in str(exc):
                raise
            self._ensure_table(db)
            row = ModelRoutingPolicyRecord(workspace_id=workspace_id, **payload.model_dump())
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._to_response(row)

    def exists(self, db: Session, workspace_id: str, use_case: str, version: str) -> bool:
        query = select(ModelRoutingPolicyRecord.id).where(
            ModelRoutingPolicyRecord.workspace_id == workspace_id,
            ModelRoutingPolicyRecord.use_case == use_case,
            ModelRoutingPolicyRecord.version == version,
        )
        try:
            return db.execute(query).first() is not None
        except OperationalError as exc:
            if "model_routing_policies" not in str(exc):
                raise
            self._ensure_table(db)
            return db.execute(query).first() is not None

    def resolve_use_case(
        self, db: Session, workspace_id: str, use_case: str
    ) -> ModelRoutingResolutionResponse:
        try:
            row = db.execute(
                select(ModelRoutingPolicyRecord)
                .where(
                    ModelRoutingPolicyRecord.workspace_id == workspace_id,
                    ModelRoutingPolicyRecord.use_case == use_case,
                    ModelRoutingPolicyRecord.status == "active",
                )
                .order_by(ModelRoutingPolicyRecord.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        except OperationalError as exc:
            if "model_routing_policies" not in str(exc):
                raise
            self._ensure_table(db)
            row = db.execute(
                select(ModelRoutingPolicyRecord)
                .where(
                    ModelRoutingPolicyRecord.workspace_id == workspace_id,
                    ModelRoutingPolicyRecord.use_case == use_case,
                    ModelRoutingPolicyRecord.status == "active",
                )
                .order_by(ModelRoutingPolicyRecord.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()

        if row is None:
            return ModelRoutingResolutionResponse(
                workspace_id=workspace_id,
                use_case=use_case,
                selected_provider="",
                selected_model="",
                status="not_configured",
                reason="No active routing policy found for this use case.",
            )

        return ModelRoutingResolutionResponse(
            workspace_id=row.workspace_id,
            use_case=row.use_case,
            selected_provider=row.primary_provider,
            selected_model=row.primary_model,
            fallback_provider=row.fallback_provider,
            fallback_model=row.fallback_model,
            policy_version=row.version,
            status=row.status,
            reason=f"Resolved using active routing policy {row.use_case}:{row.version}.",
        )

    @staticmethod
    def _to_response(row: ModelRoutingPolicyRecord) -> ModelRoutingPolicyResponse:
        return ModelRoutingPolicyResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            use_case=row.use_case,
            version=row.version,
            primary_provider=row.primary_provider,
            primary_model=row.primary_model,
            fallback_provider=row.fallback_provider,
            fallback_model=row.fallback_model,
            max_latency_ms=row.max_latency_ms,
            max_cost_usd=row.max_cost_usd,
            status=row.status,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _ensure_table(db: Session) -> None:
        inspector = inspect(db.bind)
        if "model_routing_policies" in inspector.get_table_names():
            return
        db.execute(
            text(
                """
                CREATE TABLE model_routing_policies (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    workspace_id VARCHAR(100) NOT NULL DEFAULT 'default',
                    use_case VARCHAR(100) NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    primary_provider VARCHAR(50) NOT NULL,
                    primary_model VARCHAR(100) NOT NULL,
                    fallback_provider VARCHAR(50) NOT NULL DEFAULT '',
                    fallback_model VARCHAR(100) NOT NULL DEFAULT '',
                    max_latency_ms FLOAT NOT NULL DEFAULT 1000.0,
                    max_cost_usd FLOAT NOT NULL DEFAULT 0.01,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        db.execute(text("CREATE INDEX ix_model_routing_policies_workspace_id ON model_routing_policies (workspace_id)"))
        db.execute(text("CREATE INDEX ix_model_routing_policies_use_case ON model_routing_policies (use_case)"))
        db.execute(text("CREATE INDEX ix_model_routing_policies_version ON model_routing_policies (version)"))
        db.execute(text("CREATE INDEX ix_model_routing_policies_status ON model_routing_policies (status)"))
        db.execute(
            text(
                "CREATE UNIQUE INDEX uq_model_routing_workspace_use_case_version_idx "
                "ON model_routing_policies (workspace_id, use_case, version)"
            )
        )
        db.commit()


model_routing_service = ModelRoutingService()

