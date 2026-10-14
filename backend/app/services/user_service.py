import uuid

from sqlalchemy.orm import Session

from app.core.enums import AuditAction, UserRole
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import CreateUserRequest, UpdateUserRequest
from app.services.audit_service import AuditService


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)

    def create_user(
        self, data: CreateUserRequest, actor: User, ip_address: str | None = None
    ) -> User:
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
        self.audit_service.log(
            action=AuditAction.USER_CREATED,
            entity="user",
            entity_id=str(user.id),
            user_id=actor.id,
            ip_address=ip_address,
            metadata={"email": email, "role": data.role.value, "via": "admin"},
        )
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

    def update_user(
        self,
        user_id: uuid.UUID,
        data: UpdateUserRequest,
        actor: User,
        ip_address: str | None = None,
    ) -> User:
        user = self.get_user(user_id)
        changes: dict[str, dict[str, str]] = {}

        if data.email is not None:
            new_email = data.email.lower()
            existing = self.user_repo.get_by_email(new_email)
            if existing is not None and existing.id != user.id:
                raise ConflictException("Email is already registered", "EMAIL_ALREADY_EXISTS")
            if new_email != user.email:
                changes["email"] = {"old": user.email, "new": new_email}
                user.email = new_email

        if data.name is not None and data.name != user.name:
            changes["name"] = {"old": user.name, "new": data.name}
            user.name = data.name

        if changes:
            self._log_update(actor, user, {"changes": changes}, ip_address)
        self.db.commit()
        return user

    def set_active_status(
        self, user_id: uuid.UUID, is_active: bool, actor: User, ip_address: str | None = None
    ) -> User:
        user = self.get_user(user_id)
        if user.id == actor.id and not is_active:
            # Stops an admin locking themselves (possibly the last admin) out
            raise BadRequestException("You cannot deactivate your own account", "SELF_DEACTIVATION")

        old_value = user.is_active
        user.is_active = is_active
        self._log_update(
            actor, user, {"is_active": {"old": old_value, "new": is_active}}, ip_address
        )
        self.db.commit()
        return user

    def change_role(
        self, user_id: uuid.UUID, new_role: UserRole, actor: User, ip_address: str | None = None
    ) -> User:
        user = self.get_user(user_id)
        if user.id == actor.id and new_role != UserRole.ADMIN:
            raise BadRequestException("You cannot demote your own account", "SELF_DEMOTION")

        old_role = user.role
        user.role = new_role
        self._log_update(
            actor, user, {"role": {"old": old_role.value, "new": new_role.value}}, ip_address
        )
        self.db.commit()
        return user

    def _log_update(
        self, actor: User, target: User, metadata: dict, ip_address: str | None
    ) -> None:
        self.audit_service.log(
            action=AuditAction.USER_UPDATED,
            entity="user",
            entity_id=str(target.id),
            user_id=actor.id,
            ip_address=ip_address,
            metadata=metadata,
        )