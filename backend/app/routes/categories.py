import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.enums import UserRole
from app.schemas.category import CategoryResponse, CreateCategoryRequest, UpdateCategoryRequest
from app.services.category_service import CategoryService
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/categories", tags=["Categories"])


def get_category_service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(db)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def create_category(
    data: CreateCategoryRequest, service: CategoryService = Depends(get_category_service)
):
    return service.create_category(data)


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    active_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),  # any authenticated role, no role restriction
    service: CategoryService = Depends(get_category_service),
):
    return service.list_categories(active_only)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def update_category(
    category_id: uuid.UUID,
    data: UpdateCategoryRequest,
    service: CategoryService = Depends(get_category_service),
):
    return service.update_category(category_id, data)


@router.patch(
    "/{category_id}/activate",
    response_model=CategoryResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def activate_category(
    category_id: uuid.UUID, service: CategoryService = Depends(get_category_service)
):
    return service.set_active_status(category_id, True)


@router.patch(
    "/{category_id}/deactivate",
    response_model=CategoryResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def deactivate_category(
    category_id: uuid.UUID, service: CategoryService = Depends(get_category_service)
):
    return service.set_active_status(category_id, False)