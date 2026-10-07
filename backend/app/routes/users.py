import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.enums import UserRole
from app.models.user import User
from app.schemas.auth import MessageResponse, UserResponse
from app.schemas.user import (
    ChangeRoleRequest,
    CreateUserRequest,
    PaginatedUsers,
    UpdateUserRequest,
    UserListItem,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["User Management"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def create_user(data: CreateUserRequest, service: UserService = Depends(get_user_service)):
    return service.create_user(data)


@router.get(
    "",
    response_model=PaginatedUsers,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: UserRole | None = None,
    service: UserService = Depends(get_user_service),
):
    items, total = service.list_users(page, page_size, role.value if role else None)
    return PaginatedUsers(
        items=[UserListItem.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_user(user_id: uuid.UUID, service: UserService = Depends(get_user_service)):
    return service.get_user(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def update_user(
    user_id: uuid.UUID, data: UpdateUserRequest, service: UserService = Depends(get_user_service)
):
    return service.update_user(user_id, data)


@router.patch(
    "/{user_id}/activate",
    response_model=UserResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def activate_user(user_id: uuid.UUID, service: UserService = Depends(get_user_service)):
    return service.set_active_status(user_id, True)


@router.patch(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def deactivate_user(user_id: uuid.UUID, service: UserService = Depends(get_user_service)):
    return service.set_active_status(user_id, False)


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def change_role(
    user_id: uuid.UUID, data: ChangeRoleRequest, service: UserService = Depends(get_user_service)
):
    return service.change_role(user_id, data.role)