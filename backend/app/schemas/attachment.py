import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.ticket import UserSummary


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    file_name: str
    file_type: str
    file_size: int
    uploaded_by: UserSummary
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)