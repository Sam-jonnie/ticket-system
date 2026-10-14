import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import TicketPriority, TicketStatus, UserRole
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ticket_stats(
        self,
        customer_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
    ) -> dict[str, int]:
        """
        Counts tickets by status plus overdue/critical. Optional scoping:
        customer_id limits to one customer's tickets, agent_id to tickets
        assigned to one agent. No filter = every ticket (admin view).
        """
        filters = []
        if customer_id is not None:
            filters.append(Ticket.customer_id == customer_id)
        if agent_id is not None:
            filters.append(Ticket.assigned_agent_id == agent_id)

        # One GROUP BY query gives us all four status counts at once
        status_rows = self.db.execute(
            select(Ticket.status, func.count()).where(*filters).group_by(Ticket.status)
        ).all()
        by_status = {row[0]: row[1] for row in status_rows}

        now = datetime.now(timezone.utc)
        overdue = self.db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(
                *filters,
                Ticket.due_date.is_not(None),
                Ticket.due_date < now,
                Ticket.status.not_in([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
            )
        ) or 0

        critical = self.db.scalar(
            select(func.count())
            .select_from(Ticket)
            .join(Priority, Ticket.priority_id == Priority.id)
            .where(*filters, Priority.name == TicketPriority.CRITICAL)
        ) or 0

        return {
            "total_tickets": sum(by_status.values()),
            "open_tickets": by_status.get(TicketStatus.OPEN, 0),
            "in_progress_tickets": by_status.get(TicketStatus.IN_PROGRESS, 0),
            "resolved_tickets": by_status.get(TicketStatus.RESOLVED, 0),
            "closed_tickets": by_status.get(TicketStatus.CLOSED, 0),
            "overdue_tickets": overdue,
            "critical_tickets": critical,
        }

    def count_users_by_role(self, role: UserRole, active_only: bool = False) -> int:
        query = select(func.count()).select_from(User).where(User.role == role)
        if active_only:
            query = query.where(User.is_active.is_(True))
        return self.db.scalar(query) or 0

    def tickets_per_agent(self) -> list[dict]:
        # OUTER JOIN so agents with zero tickets still appear in the list
        rows = self.db.execute(
            select(User.id, User.name, func.count(Ticket.id))
            .outerjoin(Ticket, Ticket.assigned_agent_id == User.id)
            .where(User.role == UserRole.AGENT)
            .group_by(User.id, User.name)
            .order_by(func.count(Ticket.id).desc())
        ).all()
        return [
            {"agent_id": str(r[0]), "agent_name": r[1], "ticket_count": r[2]} for r in rows
        ]