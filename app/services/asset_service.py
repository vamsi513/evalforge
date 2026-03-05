from datetime import datetime
from typing import Optional
from uuid import uuid4

import json

from sqlalchemy import delete, inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import DatasetRecord, GoldenCaseRecord, PromptTemplateRecord
from app.models.assets import (
    DatasetBundle,
    DatasetBundleImport,
    GoldenCaseCreate,
    GoldenCaseResponse,
    PromptTemplateCreate,
    PromptTemplateResponse,
)
from app.models.dataset import DatasetResponse
from app.models.eval_run import RubricCriterion


class AssetService:
    def list_prompt_templates(
        self, db: Session, dataset_name: Optional[str] = None, workspace_id: str = "default"
    ) -> list[PromptTemplateResponse]:
        query = select(PromptTemplateRecord).order_by(PromptTemplateRecord.created_at.desc())
        if dataset_name:
            if not self._dataset_exists_in_workspace(db, dataset_name, workspace_id):
                return []
            query = query.where(PromptTemplateRecord.dataset_name == dataset_name)
        else:
            dataset_names = self._workspace_dataset_names(db, workspace_id)
            if not dataset_names:
                return []
            query = query.where(PromptTemplateRecord.dataset_name.in_(dataset_names))
        rows = db.execute(query).scalars().all()
        return [self._to_prompt_response(row) for row in rows]

    def create_prompt_template(
        self, db: Session, payload: PromptTemplateCreate, workspace_id: str = "default"
    ) -> PromptTemplateResponse:
        if not self._dataset_exists_in_workspace(db, payload.dataset_name, workspace_id):
            raise ValueError("Dataset not found in workspace")
        row = PromptTemplateRecord(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._to_prompt_response(row)

    def prompt_template_exists(
        self, db: Session, dataset_name: str, version: str, workspace_id: str = "default"
    ) -> bool:
        if not self._dataset_exists_in_workspace(db, dataset_name, workspace_id):
            return False
        query = select(PromptTemplateRecord.id).where(
            PromptTemplateRecord.dataset_name == dataset_name,
            PromptTemplateRecord.version == version,
        )
        return db.execute(query).first() is not None

    def list_golden_cases(
        self, db: Session, dataset_name: Optional[str] = None, workspace_id: str = "default"
    ) -> list[GoldenCaseResponse]:
        query = select(GoldenCaseRecord).order_by(GoldenCaseRecord.created_at.desc())
        if dataset_name:
            if not self._dataset_exists_in_workspace(db, dataset_name, workspace_id):
                return []
            query = query.where(GoldenCaseRecord.dataset_name == dataset_name)
        else:
            dataset_names = self._workspace_dataset_names(db, workspace_id)
            if not dataset_names:
                return []
            query = query.where(GoldenCaseRecord.dataset_name.in_(dataset_names))
        try:
            rows = db.execute(query).scalars().all()
            return [self._to_case_response(row) for row in rows]
        except OperationalError as exc:
            if "scenario" not in str(exc):
                raise
            return self._list_legacy_golden_cases(db, dataset_name=dataset_name, workspace_id=workspace_id)

    def create_golden_case(
        self, db: Session, payload: GoldenCaseCreate, workspace_id: str = "default"
    ) -> GoldenCaseResponse:
        if not self._dataset_exists_in_workspace(db, payload.dataset_name, workspace_id):
            raise ValueError("Dataset not found in workspace")
        row = GoldenCaseRecord(
            dataset_name=payload.dataset_name,
            input_prompt=payload.input_prompt,
            expected_keyword=payload.expected_keyword,
            reference_answer=payload.reference_answer,
            scenario=payload.scenario,
            slice_name=payload.slice_name,
            severity=payload.severity,
            required_json_fields=payload.required_json_fields,
            rubric=[criterion.model_dump() for criterion in payload.rubric],
            tags=payload.tags,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return self._to_case_response(row)
        except OperationalError as exc:
            db.rollback()
            if "scenario" not in str(exc) and "slice_name" not in str(exc) and "severity" not in str(exc):
                raise
            self._ensure_golden_case_metadata_columns(db)
            legacy_id = row.id or str(uuid4())
            created_at = row.created_at or datetime.utcnow()
            db.execute(
                text(
                    """
                    INSERT INTO golden_cases (
                        id, dataset_name, input_prompt, expected_keyword, reference_answer,
                        scenario, slice_name, severity, required_json_fields, rubric, tags, created_at
                    ) VALUES (
                        :id, :dataset_name, :input_prompt, :expected_keyword, :reference_answer,
                        :scenario, :slice_name, :severity, :required_json_fields, :rubric, :tags, :created_at
                    )
                    """
                ),
                {
                    "id": legacy_id,
                    "dataset_name": payload.dataset_name,
                    "input_prompt": payload.input_prompt,
                    "expected_keyword": payload.expected_keyword,
                    "reference_answer": payload.reference_answer,
                    "scenario": payload.scenario,
                    "slice_name": payload.slice_name,
                    "severity": payload.severity,
                    "required_json_fields": json.dumps(payload.required_json_fields),
                    "rubric": json.dumps([criterion.model_dump() for criterion in payload.rubric]),
                    "tags": json.dumps(payload.tags),
                    "created_at": created_at,
                },
            )
            db.commit()
            return GoldenCaseResponse(
                id=legacy_id,
                dataset_name=payload.dataset_name,
                input_prompt=payload.input_prompt,
                expected_keyword=payload.expected_keyword,
                reference_answer=payload.reference_answer,
                scenario=payload.scenario,
                slice_name=payload.slice_name,
                severity=payload.severity,
                required_json_fields=payload.required_json_fields,
                rubric=payload.rubric,
                tags=payload.tags,
                created_at=created_at,
            )

    def get_golden_cases(
        self, db: Session, dataset_name: str, workspace_id: str = "default"
    ) -> list[GoldenCaseResponse]:
        if not self._dataset_exists_in_workspace(db, dataset_name, workspace_id):
            return []
        rows = db.execute(
            select(GoldenCaseRecord)
            .where(GoldenCaseRecord.dataset_name == dataset_name)
            .order_by(GoldenCaseRecord.created_at.asc())
        ).scalars().all()
        return [self._to_case_response(row) for row in rows]

    def export_bundle(self, db: Session, dataset_name: str, workspace_id: str = "default") -> Optional[DatasetBundle]:
        dataset_row = db.execute(
            select(DatasetRecord).where(
                DatasetRecord.name == dataset_name,
                DatasetRecord.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()
        if dataset_row is None:
            return None

        return DatasetBundle(
            dataset=DatasetResponse(
                id=dataset_row.id,
                name=dataset_row.name,
                description=dataset_row.description,
                owner=dataset_row.owner,
                workspace_id=getattr(dataset_row, "workspace_id", "default"),
                created_at=dataset_row.created_at,
            ),
            prompts=self.list_prompt_templates(db, dataset_name=dataset_name, workspace_id=workspace_id),
            golden_cases=self.list_golden_cases(db, dataset_name=dataset_name, workspace_id=workspace_id),
        )

    def import_bundle(self, db: Session, payload: DatasetBundleImport, workspace_id: str = "default") -> DatasetBundle:
        dataset_row = db.execute(
            select(DatasetRecord).where(
                DatasetRecord.name == payload.dataset.name,
                DatasetRecord.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        if dataset_row is None:
            dataset_row = DatasetRecord(workspace_id=workspace_id, **payload.dataset.model_dump())
            db.add(dataset_row)
            db.flush()
        elif payload.replace_existing:
            dataset_row.description = payload.dataset.description
            dataset_row.owner = payload.dataset.owner
            db.execute(
                delete(PromptTemplateRecord).where(
                    PromptTemplateRecord.dataset_name == payload.dataset.name
                )
            )
            db.execute(
                delete(GoldenCaseRecord).where(GoldenCaseRecord.dataset_name == payload.dataset.name)
            )

        if payload.replace_existing:
            prompt_payloads = payload.prompts
            case_payloads = payload.golden_cases
        else:
            existing_prompt_versions = {
                row.version
                for row in db.execute(
                    select(PromptTemplateRecord).where(
                        PromptTemplateRecord.dataset_name == payload.dataset.name
                    )
                ).scalars()
            }
            prompt_payloads = [
                prompt for prompt in payload.prompts if prompt.version not in existing_prompt_versions
            ]
            existing_case_keys = {
                (row.input_prompt, row.expected_keyword, row.reference_answer)
                for row in db.execute(
                    select(GoldenCaseRecord).where(GoldenCaseRecord.dataset_name == payload.dataset.name)
                ).scalars()
            }
            case_payloads = [
                case
                for case in payload.golden_cases
                if (case.input_prompt, case.expected_keyword, case.reference_answer) not in existing_case_keys
            ]

        for prompt in prompt_payloads:
            db.add(PromptTemplateRecord(**prompt.model_dump()))

        for case in case_payloads:
            db.add(
                GoldenCaseRecord(
                    dataset_name=case.dataset_name,
                    input_prompt=case.input_prompt,
                    expected_keyword=case.expected_keyword,
                    reference_answer=case.reference_answer,
                    scenario=case.scenario,
                    slice_name=case.slice_name,
                    severity=case.severity,
                    required_json_fields=case.required_json_fields,
                    rubric=[criterion.model_dump() for criterion in case.rubric],
                    tags=case.tags,
                )
            )

        db.commit()
        return self.export_bundle(db, payload.dataset.name, workspace_id=workspace_id)

    @staticmethod
    def _to_prompt_response(row: PromptTemplateRecord) -> PromptTemplateResponse:
        return PromptTemplateResponse(
            id=row.id,
            dataset_name=row.dataset_name,
            version=row.version,
            system_prompt=row.system_prompt,
            task_prompt=row.task_prompt,
            notes=row.notes,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_case_response(row: GoldenCaseRecord) -> GoldenCaseResponse:
        return GoldenCaseResponse(
            id=row.id,
            dataset_name=row.dataset_name,
            input_prompt=row.input_prompt,
            expected_keyword=row.expected_keyword,
            reference_answer=row.reference_answer,
            scenario=getattr(row, "scenario", "general"),
            slice_name=getattr(row, "slice_name", "default"),
            severity=getattr(row, "severity", "medium"),
            required_json_fields=getattr(row, "required_json_fields", []),
            rubric=[RubricCriterion(**criterion) for criterion in row.rubric],
            tags=row.tags,
            created_at=row.created_at,
        )

    @staticmethod
    def _list_legacy_golden_cases(
        db: Session, dataset_name: Optional[str] = None, workspace_id: str = "default"
    ) -> list[GoldenCaseResponse]:
        if dataset_name and not AssetService._dataset_exists_in_workspace(db, dataset_name, workspace_id):
            return []
        if not dataset_name:
            dataset_names = AssetService._workspace_dataset_names(db, workspace_id)
            if not dataset_names:
                return []
        sql = """
            SELECT id, dataset_name, input_prompt, expected_keyword, reference_answer, rubric, tags, created_at
            FROM golden_cases
        """
        params = {}
        if dataset_name:
            sql += " WHERE dataset_name = :dataset_name"
            params["dataset_name"] = dataset_name
        elif workspace_id != "default":
            placeholders = ", ".join([f":dataset_{index}" for index, _ in enumerate(dataset_names)])
            sql += f" WHERE dataset_name IN ({placeholders})"
            params.update({f"dataset_{index}": name for index, name in enumerate(dataset_names)})
        sql += " ORDER BY created_at DESC"
        rows = db.execute(text(sql), params).mappings()
        responses: list[GoldenCaseResponse] = []
        for row in rows:
            rubric = row["rubric"]
            tags = row["tags"]
            if isinstance(rubric, str):
                rubric = json.loads(rubric)
            if isinstance(tags, str):
                tags = json.loads(tags)
            responses.append(
                GoldenCaseResponse(
                    id=row["id"],
                    dataset_name=row["dataset_name"],
                    input_prompt=row["input_prompt"],
                    expected_keyword=row["expected_keyword"],
                    reference_answer=row["reference_answer"],
                    scenario="general",
                    slice_name="default",
                    severity="medium",
                    required_json_fields=[],
                    rubric=[RubricCriterion(**criterion) for criterion in rubric],
                    tags=tags,
                    created_at=row["created_at"],
                )
            )
        return responses

    @staticmethod
    def _ensure_golden_case_metadata_columns(db: Session) -> None:
        inspector = inspect(db.bind)
        existing_columns = {column["name"] for column in inspector.get_columns("golden_cases")}
        if "scenario" not in existing_columns:
            db.execute(
                text("ALTER TABLE golden_cases ADD COLUMN scenario VARCHAR(100) NOT NULL DEFAULT 'general'")
            )
        if "slice_name" not in existing_columns:
            db.execute(
                text("ALTER TABLE golden_cases ADD COLUMN slice_name VARCHAR(100) NOT NULL DEFAULT 'default'")
            )
        if "severity" not in existing_columns:
            db.execute(
                text("ALTER TABLE golden_cases ADD COLUMN severity VARCHAR(20) NOT NULL DEFAULT 'medium'")
            )
        if "required_json_fields" not in existing_columns:
            db.execute(
                text("ALTER TABLE golden_cases ADD COLUMN required_json_fields JSON NOT NULL DEFAULT '[]'")
            )
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_golden_cases_scenario ON golden_cases (scenario)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_golden_cases_slice_name ON golden_cases (slice_name)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_golden_cases_severity ON golden_cases (severity)"))
        db.commit()

    @staticmethod
    def _workspace_dataset_names(db: Session, workspace_id: str) -> list[str]:
        return [
            row.name
            for row in db.execute(
                select(DatasetRecord).where(DatasetRecord.workspace_id == workspace_id)
            ).scalars()
        ]

    @staticmethod
    def _dataset_exists_in_workspace(db: Session, dataset_name: str, workspace_id: str) -> bool:
        return db.execute(
            select(DatasetRecord.id).where(
                DatasetRecord.name == dataset_name,
                DatasetRecord.workspace_id == workspace_id,
            )
        ).first() is not None


asset_service = AssetService()
