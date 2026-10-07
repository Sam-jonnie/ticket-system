import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.models.audit_log import AuditLog


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
        Writes an audit row. Deliberately does NOT call db.commit() —
        audit logging piggybacks on whatever transaction the calling
        service is already in, so a ticket-update + its audit log
        either both succeed or both roll back together. Never call
        this after the caller's own commit().
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