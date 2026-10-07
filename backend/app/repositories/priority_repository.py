from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import TicketPriority
from app.models.priority import Priority


class PriorityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_name(self, name: TicketPriority) -> Priority | None:
        return self.db.scalar(select(Priority).where(Priority.name == name))

    def list_all(self) -> list[Priority]:
        return list(self.db.scalars(select(Priority).order_by(Priority.sla_hours)).all())