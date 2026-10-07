from datetime import datetime, timedelta, timezone

from app.models.priority import Priority


def calculate_due_date(priority: Priority, created_at: datetime | None = None) -> datetime:
    start = created_at or datetime.now(timezone.utc)
    return start + timedelta(hours=priority.sla_hours)


def is_overdue(ticket_due_date: datetime | None, ticket_status: str) -> bool:
    if ticket_due_date is None:
        return False
    if ticket_status in ("resolved", "closed"):
        return False
    return datetime.now(timezone.utc) > ticket_due_date