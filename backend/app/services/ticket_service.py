import uuid

from sqlalchemy.orm import Session

from app.core.enums import TicketPriority, TicketStatus, UserRole, VALID_STATUS_TRANSITIONS
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.repositories.priority_repository import PriorityRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ticket import CreateTicketRequest, UpdateTicketRequest
from app.utils.sla import calculate_due_date
from app.utils.ticket_number import generate_ticket_number


class TicketService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ticket_repo = TicketRepository(db)
        self.category_repo = CategoryRepository(db)
        self.priority_repo = PriorityRepository(db)
        self.user_repo = UserRepository(db)

    def create_ticket(self, current_user: User, data: CreateTicketRequest) -> Ticket:
        category = self.category_repo.get_by_id(data.category_id)
        if category is None:
            raise NotFoundException("Category not found", "CATEGORY_NOT_FOUND")
        if not category.is_active:
            raise BadRequestException(
                "This category is inactive and cannot be used for new tickets",
                "CATEGORY_INACTIVE",
            )

        priority = self.priority_repo.get_by_name(data.priority_name)
        if priority is None:
            raise NotFoundException("Priority not found", "PRIORITY_NOT_FOUND")

        ticket = Ticket(
            ticket_number=generate_ticket_number(self.db),
            title=data.title,
            description=data.description,
            status=TicketStatus.OPEN,
            customer_id=current_user.id,
            category_id=category.id,
            priority_id=priority.id,
            due_date=calculate_due_date(priority),
        )
        self.ticket_repo.create(ticket)
        self.db.commit()
        return self.ticket_repo.get_by_id(ticket.id)  # re-fetch WITH joins for the response

    def list_tickets(
        self,
        current_user: User,
        page: int,
        page_size: int,
        search: str | None,
        status_filter: TicketStatus | None,
        priority_filter: TicketPriority | None,
        category_id: uuid.UUID | None,
        assigned_agent_id: uuid.UUID | None,
        customer_id: uuid.UUID | None,
        date_from,
        date_to,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[Ticket], int]:
        # Role-based visibility scope — decided HERE, server-side, never from query params.
        restrict_customer_id = None
        restrict_agent_id = None
        if current_user.role == UserRole.CUSTOMER:
            restrict_customer_id = current_user.id
        elif current_user.role == UserRole.AGENT:
            restrict_agent_id = current_user.id
        # Admins: no restriction — see everything.

        return self.ticket_repo.list_paginated(
            page=page,
            page_size=page_size,
            search=search,
            status_filter=status_filter,
            priority_filter=priority_filter,
            category_id=category_id,
            assigned_agent_id=assigned_agent_id,
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_order=sort_order,
            restrict_customer_id=restrict_customer_id,
            restrict_agent_id=restrict_agent_id,
        )

    def get_ticket(self, current_user: User, ticket_id: uuid.UUID) -> Ticket:
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if ticket is None:
            raise NotFoundException("Ticket not found", "TICKET_NOT_FOUND")
        self._check_can_view(current_user, ticket)
        return ticket

    def update_ticket(
        self, current_user: User, ticket_id: uuid.UUID, data: UpdateTicketRequest
    ) -> Ticket:
        ticket = self.get_ticket(current_user, ticket_id)

        if ticket.status == TicketStatus.CLOSED:
            raise BadRequestException(
                "Closed tickets cannot be modified", "TICKET_CLOSED"
            )

        raw = self.ticket_repo.get_raw_by_id(ticket_id)

        if data.title is not None:
            raw.title = data.title
        if data.description is not None:
            raw.description = data.description
        if data.category_id is not None:
            category = self.category_repo.get_by_id(data.category_id)
            if category is None:
                raise NotFoundException("Category not found", "CATEGORY_NOT_FOUND")
            raw.category_id = category.id
        if data.priority_name is not None:
            priority = self.priority_repo.get_by_name(data.priority_name)
            if priority is None:
                raise NotFoundException("Priority not found", "PRIORITY_NOT_FOUND")
            raw.priority_id = priority.id
            raw.due_date = calculate_due_date(priority, raw.created_at)

        self.db.commit()
        return self.ticket_repo.get_by_id(ticket_id)

    def update_status(
        self, current_user: User, ticket_id: uuid.UUID, new_status: TicketStatus
    ) -> Ticket:
        ticket = self.get_ticket(current_user, ticket_id)

        if current_user.role == UserRole.CUSTOMER:
            raise ForbiddenException(
                "Customers cannot change ticket status", "INSUFFICIENT_ROLE"
            )

        current_status = ticket.status
        allowed_next = VALID_STATUS_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_next:
            raise BadRequestException(
                f"Cannot move ticket from {current_status.value} to {new_status.value}",
                "INVALID_STATUS_TRANSITION",
            )

        raw = self.ticket_repo.get_raw_by_id(ticket_id)
        raw.status = new_status
        self.db.commit()
        return self.ticket_repo.get_by_id(ticket_id)

    def delete_ticket(self, current_user: User, ticket_id: uuid.UUID) -> None:
        if current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Only admins can delete tickets", "INSUFFICIENT_ROLE")

        raw = self.ticket_repo.get_raw_by_id(ticket_id)
        if raw is None:
            raise NotFoundException("Ticket not found", "TICKET_NOT_FOUND")

        self.db.delete(raw)
        self.db.commit()

    # ---------- private ----------

    def _check_can_view(self, current_user: User, ticket: Ticket) -> None:
        if current_user.role == UserRole.ADMIN:
            return
        if current_user.role == UserRole.CUSTOMER and ticket.customer_id == current_user.id:
            return
        if current_user.role == UserRole.AGENT and ticket.assigned_agent_id == current_user.id:
            return
        raise ForbiddenException(
            "You do not have access to this ticket", "TICKET_ACCESS_DENIED"
        )