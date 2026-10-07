import uuid

from sqlalchemy import Enum as PgEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import TicketPriority


class Priority(Base):
    __tablename__ = "ticket_priorities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[TicketPriority] = mapped_column(
        PgEnum(
            TicketPriority,
            name="ticket_priority",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        unique=True,
        nullable=False,
    )
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<Priority {self.name.value} sla={self.sla_hours}h>"