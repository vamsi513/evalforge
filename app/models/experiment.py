from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    dataset_name: str = Field(min_length=3, max_length=100)
    owner: str = Field(min_length=2, max_length=100)
    status: str = Field(default="draft", pattern="^(draft|active|baseline|archived)$")
    description: str = Field(default="", max_length=1000)
    baseline_run_id: str = Field(default="", max_length=36)
    candidate_run_id: str = Field(default="", max_length=36)
    experiment_metadata: dict[str, str] = Field(default_factory=dict)


class ExperimentResponse(ExperimentCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str = "default"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    run_count: int = 0


class ExperimentRunTrend(BaseModel):
    run_id: str
    prompt_version: str
    model_name: str
    evaluator_version: str
    average_score: float
    created_at: datetime


class ExperimentGateTrend(BaseModel):
    gate_id: str
    status: str
    baseline_run_id: str
    candidate_run_id: str
    score_delta: float = 0.0
    failed_case_delta: int = 0
    created_at: datetime


class ExperimentReport(BaseModel):
    experiment: ExperimentResponse
    recent_runs: list[ExperimentRunTrend] = Field(default_factory=list)
    release_gates: list[ExperimentGateTrend] = Field(default_factory=list)
    score_trend: list[float] = Field(default_factory=list)
    latest_gate_status: str = ""


class ExperimentPromoteRequest(BaseModel):
    candidate_run_id: str = Field(default="", max_length=36)
    require_latest_gate_passed: bool = True


class ExperimentPromoteResponse(BaseModel):
    experiment_name: str
    workspace_id: str = "default"
    promoted_run_id: str
    gate_id: str
    gate_status: str
    message: str
    updated_experiment: ExperimentResponse


class ExperimentPromotionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str = "default"
    experiment_name: str
    dataset_name: str
    gate_id: str
    promoted_run_id: str
    actor: str = "system"
    note: str = ""
    event_metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
