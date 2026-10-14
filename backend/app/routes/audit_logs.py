import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.enums import AuditAction, UserRole
from app.schemas.audit import AuditLogResponse, PaginatedAuditLogs
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    return AuditService(db)


# The ONLY audit route is a read. There is deliberately no POST/PUT/PATCH/DELETE.
@router.get(
    "",
    response_model=PaginatedAuditLogs,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: AuditAction | None = None,
    user_id: uuid.UUID | None = None,
    entity: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    service: AuditService = Depends(get_audit_service),
):
    rows, total = service.list_logs(
        page, page_size, action, user_id, entity, entity_id, date_from, date_to
    )
    return PaginatedAuditLogs(
        items=[AuditLogResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )