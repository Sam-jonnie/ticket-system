import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: uuid.UUID, token: str, expires_at: datetime) -> RefreshToken:
        row = RefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        self.db.add(row)
        self.db.flush()
        return row

    def get_by_token(self, token: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.token == token))

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False))
            .values(is_revoked=True)
        )