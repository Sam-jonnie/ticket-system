import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        action: AuditAction,
        entity: str,
        entity_id: str | None = None,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Writes an audit row. Deliberately does NOT commit: audit logging joins
        the caller's transaction, so an action and its audit row succeed or
        fail together. Always call this BEFORE the caller's own commit().
        """
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip_address=ip_address,
            metadata_=metadata,
        )
        self.db.add(entry)

    def list_logs(
        self,
        page: int,
        page_size: int,
        action: AuditAction | None = None,
        user_id: uuid.UUID | None = None,
        entity: str | None = None,
        entity_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        return AuditLogRepository(self.db).list_paginated(
            page, page_size, action, user_id, entity, entity_id, date_from, date_to
        )