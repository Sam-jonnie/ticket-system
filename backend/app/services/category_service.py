import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CreateCategoryRequest, UpdateCategoryRequest


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CategoryRepository(db)

    def create_category(self, data: CreateCategoryRequest) -> Category:
        if self.repo.get_by_name(data.name) is not None:
            raise ConflictException("Category already exists", "CATEGORY_ALREADY_EXISTS")
        category = Category(name=data.name, description=data.description)
        self.repo.create(category)
        self.db.commit()
        return category

    def list_categories(self, active_only: bool = False) -> list[Category]:
        return self.repo.list_all(active_only)

    def get_category(self, category_id: uuid.UUID) -> Category:
        category = self.repo.get_by_id(category_id)
        if category is None:
            raise NotFoundException("Category not found", "CATEGORY_NOT_FOUND")
        return category

    def update_category(self, category_id: uuid.UUID, data: UpdateCategoryRequest) -> Category:
        category = self.get_category(category_id)
        if data.name is not None:
            category.name = data.name
        if data.description is not None:
            category.description = data.description
        self.db.commit()
        return category

    def set_active_status(self, category_id: uuid.UUID, is_active: bool) -> Category:
        category = self.get_category(category_id)
        category.is_active = is_active
        self.db.commit()
        return category