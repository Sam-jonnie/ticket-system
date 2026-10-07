import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import UserRole


class CreateUserRequest(BaseModel):
    """Admin creates a user directly — can set any role, unlike public /auth/register."""

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole

    model_config = ConfigDict(str_strip_whitespace=True)


class UpdateUserRequest(BaseModel):
    """All fields optional — only provided ones get changed (PATCH semantics)."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ChangeRoleRequest(BaseModel):
    role: UserRole


class UserListItem(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedUsers(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int