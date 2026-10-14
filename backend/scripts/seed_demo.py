"""
Idempotent demo data. Safe to run more than once.
    python scripts/seed_demo.py
These are DEMO credentials for local development only.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.enums import TicketPriority, UserRole
from app.core.security import hash_password
from app.models.category import Category
from app.models.priority import Priority
from app.models.user import User

SLA_HOURS = {
    TicketPriority.LOW: 72,
    TicketPriority.MEDIUM: 48,
    TicketPriority.HIGH: 24,
    TicketPriority.CRITICAL: 4,
}

CATEGORIES = {
    "Technical Support": "Errors, bugs and anything not working",
    "Billing": "Invoices, payments and refunds",
    "Account": "Login, profile and access problems",
    "Product Issue": "Problems with the product itself",
    "General": "Everything else",
}

DEMO_USERS = [
    ("Admin User", "admin@example.com", "Admin@12345", UserRole.ADMIN),
    ("Agent One", "agent1@example.com", "Agent@12345", UserRole.AGENT),
    ("Agent Two", "agent2@example.com", "Agent@12345", UserRole.AGENT),
    ("Customer One", "customer1@example.com", "Customer@12345", UserRole.CUSTOMER),
    ("Customer Two", "customer2@example.com", "Customer@12345", UserRole.CUSTOMER),
]


def seed() -> None:
    with SessionLocal() as db:
        for priority_name, hours in SLA_HOURS.items():
            if db.scalar(select(Priority).where(Priority.name == priority_name)) is None:
                db.add(Priority(name=priority_name, sla_hours=hours))
                print(f"+ priority {priority_name.value} ({hours}h SLA)")

        for name, description in CATEGORIES.items():
            if db.scalar(select(Category).where(Category.name == name)) is None:
                db.add(Category(name=name, description=description))
                print(f"+ category {name}")

        for name, email, password, role in DEMO_USERS:
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(
                    User(name=name, email=email, hashed_password=hash_password(password), role=role)
                )
                print(f"+ {role.value}: {email}")

        db.commit()
    print("Done.")


if __name__ == "__main__":
    seed()