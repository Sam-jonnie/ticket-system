# backend/scripts/seed_priorities.py
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.core.enums import TicketPriority
from app.models.priority import Priority

SLA_HOURS = {
    TicketPriority.LOW: 72,
    TicketPriority.MEDIUM: 48,
    TicketPriority.HIGH: 24,
    TicketPriority.CRITICAL: 4,
}


def seed_priorities() -> None:
    db = SessionLocal()
    try:
        for priority_enum, hours in SLA_HOURS.items():
            existing = db.query(Priority).filter(Priority.name == priority_enum).first()
            if existing is not None:
                print(f"{priority_enum.value} already exists, skipping")
                continue
            db.add(Priority(name=priority_enum, sla_hours=hours))
            print(f"Created {priority_enum.value} -> {hours}h SLA")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_priorities()