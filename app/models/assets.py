from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.dataset import DatasetCreate, DatasetResponse
from app.models.eval_run import RubricCriterion


class PromptTemplateCreate(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    system_prompt: str = Field(min_length=10, max_length=4000)
    task_prompt: str = Field(min_length=10, max_length=4000)
    notes: str = Field(default="", max_length=1000)


class PromptTemplateResponse(PromptTemplateCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GoldenCaseCreate(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=100)
    input_prompt: str = Field(min_length=5, max_length=4000)
    expected_keyword: str = Field(min_length=1, max_length=200)
    reference_answer: str = Field(default="", max_length=4000)
    scenario: str = Field(default="general", min_length=2, max_length=100)
    slice_name: str = Field(default="default", min_length=2, max_length=100)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    required_json_fields: list[str] = Field(default_factory=list, max_length=20)
    rubric: list[RubricCriterion] = Field(default_factory=list, max_length=10)
    tags: list[str] = Field(default_factory=list, max_length=20)


class GoldenCaseResponse(GoldenCaseCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StoredEvalRunCreate(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    candidate_outputs: list[str] = Field(min_length=1, max_length=1000)


class DatasetBundle(BaseModel):
    dataset: DatasetResponse
    prompts: list[PromptTemplateResponse] = Field(default_factory=list)
    golden_cases: list[GoldenCaseResponse] = Field(default_factory=list)
    exported_at: datetime = Field(default_factory=datetime.utcnow)


class DatasetBundleImport(BaseModel):
    dataset: DatasetCreate
    prompts: list[PromptTemplateCreate] = Field(default_factory=list)
    golden_cases: list[GoldenCaseCreate] = Field(default_factory=list)
    replace_existing: bool = False
