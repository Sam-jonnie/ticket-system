import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class TicketComment(TimestampMixin, Base):
    __tablename__ = "ticket_comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<TicketComment ticket_id={self.ticket_id} user_id={self.user_id}>"