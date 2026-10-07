import uuid

from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import CreateUserRequest, UpdateUserRequest


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    def create_user(self, data: CreateUserRequest) -> User:
        email = data.email.lower()
        if self.user_repo.get_by_email(email) is not None:
            raise ConflictException("Email is already registered", "EMAIL_ALREADY_EXISTS")

        user = User(
            name=data.name,
            email=email,
            hashed_password=hash_password(data.password),
            role=data.role,
        )
        self.user_repo.create(user)
        self.db.commit()
        return user

    def list_users(
        self, page: int, page_size: int, role: str | None = None
    ) -> tuple[list[User], int]:
        return self.user_repo.list_paginated(page, page_size, role)

    def get_user(self, user_id: uuid.UUID) -> User:
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found", "USER_NOT_FOUND")
        return user

    def update_user(self, user_id: uuid.UUID, data: UpdateUserRequest) -> User:
        user = self.get_user(user_id)

        if data.email is not None:
            new_email = data.email.lower()
            existing = self.user_repo.get_by_email(new_email)
            if existing is not None and existing.id != user.id:
                raise ConflictException("Email is already registered", "EMAIL_ALREADY_EXISTS")
            user.email = new_email

        if data.name is not None:
            user.name = data.name

        self.db.commit()
        return user

    def set_active_status(self, user_id: uuid.UUID, is_active: bool) -> User:
        user = self.get_user(user_id)
        user.is_active = is_active
        self.db.commit()
        return user

    def change_role(self, user_id: uuid.UUID, new_role: UserRole) -> User:
        user = self.get_user(user_id)
        user.role = new_role
        self.db.commit()
        return user