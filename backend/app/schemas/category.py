import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class UpdateCategoryRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)