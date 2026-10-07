# app/repositories/comment_repository.py
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.ticket_comment import TicketComment
from app.models.user import User


class CommentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, comment: TicketComment) -> TicketComment:
        self.db.add(comment)
        self.db.flush()
        return comment

    def get_by_id(self, comment_id: uuid.UUID) -> TicketComment | None:
        return self.db.get(TicketComment, comment_id)

    def list_for_ticket(self, ticket_id: uuid.UUID) -> list[tuple[TicketComment, User]]:
        rows = self.db.execute(
            select(TicketComment, User)
            .join(User, TicketComment.user_id == User.id)
            .where(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.created_at.asc())
        ).all()
        return [(c, u) for c, u in rows]