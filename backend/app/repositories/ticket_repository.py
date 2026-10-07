# app/repositories/ticket_repository.py
import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.enums import TicketPriority, TicketStatus
from app.models.category import Category
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User


class TicketRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _base_query(self):
        customer = aliased(User, name="customer")
        agent = aliased(User, name="agent")

        query = (
            select(Ticket, customer, agent, Category, Priority)
            .join(customer, Ticket.customer_id == customer.id)
            .outerjoin(agent, Ticket.assigned_agent_id == agent.id)
            .join(Category, Ticket.category_id == Category.id)
            .join(Priority, Ticket.priority_id == Priority.id)
        )
        return query, customer, agent

    def _row_to_ticket(self, row) -> Ticket:
        ticket, customer, agent, category, priority = row
        ticket.customer = customer
        ticket.assigned_agent = agent
        ticket.category = category
        ticket.priority = priority
        return ticket

    def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        query, *_ = self._base_query()
        row = self.db.execute(query.where(Ticket.id == ticket_id)).first()
        return self._row_to_ticket(row) if row else None

    def get_raw_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        """Plain fetch, no joins — used internally when we just need to mutate the row."""
        return self.db.get(Ticket, ticket_id)

    def count_all(self) -> int:
        return self.db.scalar(select(func.count()).select_from(Ticket)) or 0

    def create(self, ticket: Ticket) -> Ticket:
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def list_paginated(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status_filter: TicketStatus | None = None,
        priority_filter: TicketPriority | None = None,
        category_id: uuid.UUID | None = None,
        assigned_agent_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        restrict_customer_id: uuid.UUID | None = None,
        restrict_agent_id: uuid.UUID | None = None,
    ) -> tuple[list[Ticket], int]:
        query, customer, agent = self._base_query()
        conditions = []

        if search:
            like_pattern = f"%{search}%"
            conditions.append(
                or_(Ticket.title.ilike(like_pattern), Ticket.description.ilike(like_pattern))
            )
        if status_filter is not None:
            conditions.append(Ticket.status == status_filter)
        if priority_filter is not None:
            conditions.append(Priority.name == priority_filter)
        if category_id is not None:
            conditions.append(Ticket.category_id == category_id)
        if assigned_agent_id is not None:
            conditions.append(Ticket.assigned_agent_id == assigned_agent_id)
        if customer_id is not None:
            conditions.append(Ticket.customer_id == customer_id)
        if date_from is not None:
            conditions.append(Ticket.created_at >= date_from)
        if date_to is not None:
            conditions.append(Ticket.created_at <= date_to)

        # Role-based scoping — enforced here, not just trusted from the caller,
        # so a customer can NEVER see another customer's tickets no matter what
        # query params they send.
        if restrict_customer_id is not None:
            conditions.append(Ticket.customer_id == restrict_customer_id)
        if restrict_agent_id is not None:
            conditions.append(Ticket.assigned_agent_id == restrict_agent_id)

        if conditions:
            query = query.where(and_(*conditions))

        # Count total matching rows BEFORE pagination (for the response's "total")
        count_query = select(func.count()).select_from(Ticket).join(
            Priority, Ticket.priority_id == Priority.id
        )
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total = self.db.scalar(count_query) or 0

        sort_column_map = {
            "created_at": Ticket.created_at,
            "updated_at": Ticket.updated_at,
            "due_date": Ticket.due_date,
            "title": Ticket.title,
            "status": Ticket.status,
        }
        sort_column = sort_column_map.get(sort_by, Ticket.created_at)
        query = query.order_by(
            sort_column.desc() if sort_order == "desc" else sort_column.asc()
        )

        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = self.db.execute(query).all()
        tickets = [self._row_to_ticket(row) for row in rows]

        return tickets, total