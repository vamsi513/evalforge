from datetime import datetime
from typing import Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class RubricCriterion(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=300)
    weight: float = Field(gt=0.0, le=1.0)
    required_terms: list[str] = Field(default_factory=list, max_length=10)


class EvalSample(BaseModel):
    prompt: str = Field(min_length=5)
    expected_keyword: str = Field(min_length=1)
    candidate_output: str = Field(min_length=1)
    reference_answer: Optional[str] = Field(default=None, max_length=2000)
    rubric: list[RubricCriterion] = Field(default_factory=list, max_length=10)


class EvalRunCreate(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=100)
    experiment_name: str = Field(default="", max_length=100)
    prompt_version: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    evaluator_version: str = Field(default="heuristic-v1", min_length=1, max_length=50)
    run_metadata: dict[str, str] = Field(default_factory=dict)
    samples: list[EvalSample] = Field(min_length=1, max_length=1000)


class EvalCaseResult(EvalSample):
    score: float
    latency_ms: int
    cost_usd: float
    passed: bool
    matched_terms: list[str] = Field(default_factory=list)
    missing_terms: list[str] = Field(default_factory=list)
    criterion_scores: dict[str, float] = Field(default_factory=dict)
    feedback: str


class EvalRunResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    dataset_name: str
    experiment_name: str = ""
    prompt_version: str
    model_name: str
    evaluator_version: str = "heuristic-v1"
    average_score: float
    run_metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    results: list[EvalCaseResult]


class PairwiseSample(BaseModel):
    prompt: str = Field(min_length=5)
    candidate_a: str = Field(min_length=1)
    candidate_b: str = Field(min_length=1)
    expected_keyword: str = Field(min_length=1)
    reference_answer: Optional[str] = Field(default=None, max_length=2000)
    rubric: list[RubricCriterion] = Field(default_factory=list, max_length=10)


class PairwiseEvalCreate(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=100)
    prompt_version_a: str = Field(min_length=1, max_length=50)
    prompt_version_b: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    samples: list[PairwiseSample] = Field(min_length=1, max_length=1000)


class PairwiseCaseResult(BaseModel):
    prompt: str
    score_a: float
    score_b: float
    winner: str
    rationale: str


class PairwiseEvalResponse(BaseModel):
    dataset_name: str
    prompt_version_a: str
    prompt_version_b: str
    model_name: str
    win_rate_a: float
    win_rate_b: float
    ties: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    results: list[PairwiseCaseResult]


class JudgeEvalCreate(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    samples: list[EvalSample] = Field(min_length=1, max_length=1000)


class JudgeCaseResult(EvalCaseResult):
    judge_provider: str
    judge_model: str
    judge_score: float
    judge_reasoning: str
    used_fallback: bool = False


class JudgeEvalResponse(BaseModel):
    dataset_name: str
    prompt_version: str
    model_name: str
    judge_provider: str
    judge_model: str
    average_score: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    results: list[JudgeCaseResult]


class AsyncEvalJobResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: str
    status: str
    dataset_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: str = ""
    result: Optional[EvalRunResponse] = None


class ReleaseGateCreate(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=100)
    baseline_run_id: str = Field(min_length=36, max_length=36)
    candidate_run_id: str = Field(min_length=36, max_length=36)
    min_score_delta: float = Field(default=-0.02, ge=-1.0, le=1.0)
    max_latency_regression_ms: float = Field(default=25.0, ge=0.0)
    max_cost_regression_usd: float = Field(default=0.001, ge=0.0)
    max_failed_case_delta: int = Field(default=0, ge=0)


class ReleaseGateResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    dataset_name: str
    baseline_run_id: str
    candidate_run_id: str
    status: str
    summary: str
    metrics: dict[str, Union[float, int]] = Field(default_factory=dict)
    failures: list[dict[str, str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
