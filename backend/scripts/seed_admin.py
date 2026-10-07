import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.core.enums import UserRole
from app.core.security import hash_password
from app.models.user import User


def seed_admin() -> None:
    db = SessionLocal()
    try:
        email = input("Admin email: ").strip().lower()
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            print(f"A user with email '{email}' already exists (role={existing.role.value}).")
            return

        name = input("Admin name: ").strip()
        password = input("Admin password (min 8 chars): ").strip()

        admin = User(
            name=name,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(admin)
        db.commit()
        print(f"Admin '{email}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()