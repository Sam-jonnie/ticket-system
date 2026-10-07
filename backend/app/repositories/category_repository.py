import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, category_id: uuid.UUID) -> Category | None:
        return self.db.get(Category, category_id)

    def get_by_name(self, name: str) -> Category | None:
        return self.db.scalar(select(Category).where(Category.name == name))

    def list_all(self, active_only: bool = False) -> list[Category]:
        query = select(Category).order_by(Category.name)
        if active_only:
            query = query.where(Category.is_active.is_(True))
        return list(self.db.scalars(query).all())

    def create(self, category: Category) -> Category:
        self.db.add(category)
        self.db.flush()
        return category