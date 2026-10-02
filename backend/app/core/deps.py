import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.security import decode_token
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.models.user import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None or payload.get("type") != "access":
        raise UnauthorizedException("Invalid or expired access token", "INVALID_TOKEN")

    user_id = uuid.UUID(payload["sub"])
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise UnauthorizedException("User not found or inactive", "USER_INACTIVE")

    return user


def require_roles(*allowed_roles: UserRole):

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                "You do not have permission to perform this action", "INSUFFICIENT_ROLE"
            )
        return current_user

    return role_checker