import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ticket_attachment import TicketAttachment
from app.models.user import User


class AttachmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, attachment: TicketAttachment) -> TicketAttachment:
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def get_by_id(self, attachment_id: uuid.UUID) -> TicketAttachment | None:
        return self.db.get(TicketAttachment, attachment_id)

    def list_for_ticket(self, ticket_id: uuid.UUID) -> list[tuple[TicketAttachment, User]]:
        rows = self.db.execute(
            select(TicketAttachment, User)
            .join(User, TicketAttachment.uploaded_by_id == User.id)
            .where(TicketAttachment.ticket_id == ticket_id)
            .order_by(TicketAttachment.created_at.desc())
        ).all()
        return [(a, u) for a, u in rows]

    def delete(self, attachment: TicketAttachment) -> None:
        self.db.delete(attachment)