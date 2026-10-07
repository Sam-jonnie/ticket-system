# app/models/ticket.py
import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum, ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import TicketStatus
from app.models.mixins import TimestampMixin


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    ticket_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[TicketStatus] = mapped_column(
        PgEnum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=TicketStatus.OPEN,
        index=True,
    )

    # Relationships (foreign keys)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ticket_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    priority_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ticket_priorities.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def __repr__(self) -> str:
        return f"<Ticket {self.ticket_number} status={self.status.value}>"