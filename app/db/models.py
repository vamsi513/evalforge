from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DatasetRecord(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("name", name="uq_dataset_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EvalRunRecord(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    experiment_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(50), nullable=False, default="heuristic-v1")
    average_score: Mapped[float] = mapped_column(Float, nullable=False)
    run_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ExperimentRecord(Base):
    __tablename__ = "experiments"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_experiment_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    baseline_run_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    candidate_run_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    experiment_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class EvaluatorDefinitionRecord(Base):
    __tablename__ = "evaluator_definitions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_evaluator_name_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ModelRoutingPolicyRecord(Base):
    __tablename__ = "model_routing_policies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "use_case", "version", name="uq_model_routing_workspace_use_case_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    use_case: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    primary_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    primary_model: Mapped[str] = mapped_column(String(100), nullable=False)
    fallback_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    fallback_model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    max_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    max_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.01)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class EvalJobRecord(Base):
    __tablename__ = "eval_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PromptTemplateRecord(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("dataset_name", "version", name="uq_prompt_template_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    task_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class GoldenCaseRecord(Base):
    __tablename__ = "golden_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scenario: Mapped[str] = mapped_column(String(100), nullable=False, default="general", index=True)
    slice_name: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    required_json_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rubric: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReleaseGateDecisionRecord(Base):
    __tablename__ = "release_gate_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    experiment_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    baseline_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    failures: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ExperimentPromotionEventRecord(Base):
    __tablename__ = "experiment_promotion_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    experiment_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    gate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    promoted_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
