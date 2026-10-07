import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class TicketAttachment(TimestampMixin, Base):
    __tablename__ = "ticket_attachments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)  # detected MIME type
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)   # bytes
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    def __repr__(self) -> str:
        return f"<TicketAttachment {self.file_name}>"