from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ticket import Ticket


def generate_ticket_number(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(Ticket)) or 0
    next_number = count + 1
    return f"TKT-{next_number:05d}"