from typing import Optional

from sqlalchemy import delete, select
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
        self, db: Session, dataset_name: Optional[str] = None
    ) -> list[PromptTemplateResponse]:
        query = select(PromptTemplateRecord).order_by(PromptTemplateRecord.created_at.desc())
        if dataset_name:
            query = query.where(PromptTemplateRecord.dataset_name == dataset_name)
        rows = db.execute(query).scalars().all()
        return [self._to_prompt_response(row) for row in rows]

    def create_prompt_template(self, db: Session, payload: PromptTemplateCreate) -> PromptTemplateResponse:
        row = PromptTemplateRecord(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._to_prompt_response(row)

    def prompt_template_exists(self, db: Session, dataset_name: str, version: str) -> bool:
        query = select(PromptTemplateRecord.id).where(
            PromptTemplateRecord.dataset_name == dataset_name,
            PromptTemplateRecord.version == version,
        )
        return db.execute(query).first() is not None

    def list_golden_cases(self, db: Session, dataset_name: Optional[str] = None) -> list[GoldenCaseResponse]:
        query = select(GoldenCaseRecord).order_by(GoldenCaseRecord.created_at.desc())
        if dataset_name:
            query = query.where(GoldenCaseRecord.dataset_name == dataset_name)
        rows = db.execute(query).scalars().all()
        return [self._to_case_response(row) for row in rows]

    def create_golden_case(self, db: Session, payload: GoldenCaseCreate) -> GoldenCaseResponse:
        row = GoldenCaseRecord(
            dataset_name=payload.dataset_name,
            input_prompt=payload.input_prompt,
            expected_keyword=payload.expected_keyword,
            reference_answer=payload.reference_answer,
            rubric=[criterion.model_dump() for criterion in payload.rubric],
            tags=payload.tags,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._to_case_response(row)

    def get_golden_cases(self, db: Session, dataset_name: str) -> list[GoldenCaseResponse]:
        rows = db.execute(
            select(GoldenCaseRecord)
            .where(GoldenCaseRecord.dataset_name == dataset_name)
            .order_by(GoldenCaseRecord.created_at.asc())
        ).scalars().all()
        return [self._to_case_response(row) for row in rows]

    def export_bundle(self, db: Session, dataset_name: str) -> Optional[DatasetBundle]:
        dataset_row = db.execute(
            select(DatasetRecord).where(DatasetRecord.name == dataset_name)
        ).scalar_one_or_none()
        if dataset_row is None:
            return None

        return DatasetBundle(
            dataset=DatasetResponse(
                id=dataset_row.id,
                name=dataset_row.name,
                description=dataset_row.description,
                owner=dataset_row.owner,
                created_at=dataset_row.created_at,
            ),
            prompts=self.list_prompt_templates(db, dataset_name=dataset_name),
            golden_cases=self.list_golden_cases(db, dataset_name=dataset_name),
        )

    def import_bundle(self, db: Session, payload: DatasetBundleImport) -> DatasetBundle:
        dataset_row = db.execute(
            select(DatasetRecord).where(DatasetRecord.name == payload.dataset.name)
        ).scalar_one_or_none()

        if dataset_row is None:
            dataset_row = DatasetRecord(**payload.dataset.model_dump())
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
                    rubric=[criterion.model_dump() for criterion in case.rubric],
                    tags=case.tags,
                )
            )

        db.commit()
        return self.export_bundle(db, payload.dataset.name)

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
            rubric=[RubricCriterion(**criterion) for criterion in row.rubric],
            tags=row.tags,
            created_at=row.created_at,
        )


asset_service = AssetService()
