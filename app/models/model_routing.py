from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ModelRoutingPolicyCreate(BaseModel):
    use_case: str = Field(min_length=2, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    primary_provider: str = Field(min_length=2, max_length=50)
    primary_model: str = Field(min_length=2, max_length=100)
    fallback_provider: str = Field(default="", max_length=50)
    fallback_model: str = Field(default="", max_length=100)
    max_latency_ms: float = Field(default=1000.0, ge=0.0)
    max_cost_usd: float = Field(default=0.01, ge=0.0)
    status: str = Field(default="active", pattern="^(draft|active|deprecated|archived)$")
    notes: str = Field(default="", max_length=1000)


class ModelRoutingPolicyResponse(ModelRoutingPolicyCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str = "default"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ModelRoutingResolutionResponse(BaseModel):
    workspace_id: str = "default"
    use_case: str
    selected_provider: str
    selected_model: str
    fallback_provider: str = ""
    fallback_model: str = ""
    policy_version: str = ""
    status: str = "not_configured"
    reason: str = ""

