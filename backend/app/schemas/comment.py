import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ticket import UserSummary


class CreateCommentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(str_strip_whitespace=True)


class UpdateCommentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(str_strip_whitespace=True)


class CommentResponse(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    user: UserSummary
    message: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)