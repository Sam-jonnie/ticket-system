# app/schemas/notification.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import NotificationType


class NotificationResponse(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID | None
    type: NotificationType
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)