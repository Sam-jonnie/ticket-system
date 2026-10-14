import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.enums import UserRole
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.user import (
    ChangeRoleRequest,
    CreateUserRequest,
    PaginatedUsers,
    UpdateUserRequest,
    UserListItem,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["User Management"])

require_admin = require_roles(UserRole.ADMIN)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: CreateUserRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    return service.create_user(data, current_user, request.client.host)


@router.get("", response_model=PaginatedUsers, dependencies=[Depends(require_admin)])
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


@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_admin)])
def get_user(user_id: uuid.UUID, service: UserService = Depends(get_user_service)):
    return service.get_user(user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    data: UpdateUserRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    return service.update_user(user_id, data, current_user, request.client.host)


@router.patch("/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    return service.set_active_status(user_id, True, current_user, request.client.host)


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    return service.set_active_status(user_id, False, current_user, request.client.host)


@router.patch("/{user_id}/role", response_model=UserResponse)
def change_role(
    user_id: uuid.UUID,
    data: ChangeRoleRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    return service.change_role(user_id, data.role, current_user, request.client.host)