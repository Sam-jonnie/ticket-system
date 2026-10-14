import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog


class AuditLogRepository:
    """Read-only on purpose: rows are written by AuditService.log() and never changed."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_paginated(
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
        conditions = []
        if action is not None:
            conditions.append(AuditLog.action == action)
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if entity is not None:
            conditions.append(AuditLog.entity == entity)
        if entity_id is not None:
            conditions.append(AuditLog.entity_id == entity_id)
        if date_from is not None:
            conditions.append(AuditLog.created_at >= date_from)
        if date_to is not None:
            conditions.append(AuditLog.created_at <= date_to)

        total = self.db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
        rows = self.db.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total