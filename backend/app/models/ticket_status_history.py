# app/models/ticket_status_history.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as PgEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import TicketStatus


class TicketStatusHistory(Base):
    __tablename__ = "ticket_status_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Nullable because this table doubles as an assignment log: a row can
    # represent EITHER a status change OR an assignment change (not both),
    # so only the relevant pair of columns gets filled in per row.
    old_status: Mapped[TicketStatus | None] = mapped_column(
        PgEnum(TicketStatus, name="ticket_status", values_callable=lambda e: [m.value for m in e]),
        default=None,
    )
    new_status: Mapped[TicketStatus | None] = mapped_column(
        PgEnum(TicketStatus, name="ticket_status", values_callable=lambda e: [m.value for m in e]),
        default=None,
    )
    old_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    new_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    note: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TicketStatusHistory ticket_id={self.ticket_id}>"