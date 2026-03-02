from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=10, max_length=500)
    owner: str = Field(min_length=2, max_length=100)


class DatasetResponse(DatasetCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

