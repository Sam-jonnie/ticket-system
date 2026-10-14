import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AuditAction


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: AuditAction
    entity: str
    entity_id: str | None
    ip_address: str | None
    # The ORM attribute is metadata_ (plain "metadata" is reserved by SQLAlchemy),
    # but the JSON we send out is called "metadata".
    metadata_: dict[str, Any] | None = Field(default=None, serialization_alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("ip_address", mode="before")
    @classmethod
    def _ip_to_string(cls, value: Any) -> str | None:
        # Postgres INET can arrive as an ipaddress object, e.g. 127.0.0.1/32
        return None if value is None else str(value).split("/")[0]


class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int