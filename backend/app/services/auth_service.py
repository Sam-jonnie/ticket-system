from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import AuditAction, UserRole
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)
        self.audit_service  = AuditService(db)

    # ---------- public methods ----------

    def register(self, data: RegisterRequest) -> User:
        email = data.email.lower()
        if self.user_repo.get_by_email(email) is not None:
            raise ConflictException("Email is already registered", "EMAIL_ALREADY_EXISTS")

        user = User(
            name=data.name,
            email=email,
            hashed_password=hash_password(data.password),
            role=UserRole.CUSTOMER,  # public signup is ALWAYS customer
        )
        self.user_repo.create(user)
        self.db.commit()
        return user

    def login(self, email: str, password: str) -> TokenResponse:
        user = self.user_repo.get_by_email(email.lower())

        # Same error for "no such user" and "wrong password" so attackers
        # can't discover which emails exist.
        if user is None or not verify_password(password, user.hashed_password):
            self.audit_service.log(
                action=AuditAction.FAILED_LOGIN,
                entity="user",
                entity_id=email,  # log the attempted email even if no such user exists
                ip_address=ip_address,
            )
            self.db.commit()  # commit the audit row even though login itself failed
            raise UnauthorizedException("Invalid email or password", "INVALID_CREDENTIALS")
        
        if not user.is_active:
            raise ForbiddenException("This account is deactivated", "ACCOUNT_INACTIVE")

        tokens = self._issue_tokens(user)
        self.audit_service.log(
            action=AuditAction.LOGIN,
            entity="user",
            entity_id=str(user.id),
            user_id=user.id,
            ip_address=ip_address,
        )
        self.db.commit()
        return tokens
    
    def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid refresh token", "INVALID_REFRESH_TOKEN")

        stored = self.token_repo.get_by_token(refresh_token)
        now = datetime.now(timezone.utc)
        if stored is None or stored.is_revoked or stored.expires_at <= now:
            raise UnauthorizedException("Refresh token expired or revoked", "INVALID_REFRESH_TOKEN")

        user = self.user_repo.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedException("User not found or inactive", "USER_INACTIVE")

        stored.is_revoked = True  # rotation: each refresh token works only once
        tokens = self._issue_tokens(user)
        self.db.commit()
        return tokens

    def logout(self, user: User, refresh_token: str) -> None:
        stored = self.token_repo.get_by_token(refresh_token)
        if stored is not None and stored.user_id == user.id:
            stored.is_revoked = True
            self.db.commit()

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise UnauthorizedException("Current password is incorrect", "INVALID_CREDENTIALS")

        user.hashed_password = hash_password(new_password)
        self.token_repo.revoke_all_for_user(user.id)  # force re-login everywhere
        self.db.commit()

    # ---------- private helpers ----------

    def _issue_tokens(self, user: User) -> TokenResponse:
        access = create_access_token(user.id, user.role.value)
        refresh = create_refresh_token(user.id)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        self.token_repo.create(user.id, refresh, expires_at)
        return TokenResponse(access_token=access, refresh_token=refresh)