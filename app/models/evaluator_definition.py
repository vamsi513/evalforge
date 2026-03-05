from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class EvaluatorDefinitionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    kind: str = Field(min_length=2, max_length=50)
    status: str = Field(default="active", pattern="^(draft|active|deprecated|archived)$")
    description: str = Field(default="", max_length=1000)
    config: dict[str, str] = Field(default_factory=dict)


class EvaluatorDefinitionResponse(EvaluatorDefinitionCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

