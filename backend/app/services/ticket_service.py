import uuid
from datetime import datetime

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.enums import (
    AuditAction,
    NotificationType,
    TicketPriority,
    TicketStatus,
    UserRole,
    VALID_STATUS_TRANSITIONS,
)
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.repositories.priority_repository import PriorityRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ticket import CreateTicketRequest, UpdateTicketRequest
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.utils.sla import calculate_due_date
from app.utils.ticket_number import generate_ticket_number


class TicketService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ticket_repo = TicketRepository(db)
        self.category_repo = CategoryRepository(db)
        self.priority_repo = PriorityRepository(db)
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)

    # ---------- create ----------

    def create_ticket(
        self,
        current_user: User,
        data: CreateTicketRequest,
        background_tasks: BackgroundTasks,
        ip_address: str | None = None,
    ) -> Ticket:
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

        self.audit_service.log(
            action=AuditAction.TICKET_CREATED,
            entity="ticket",
            entity_id=str(ticket.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata={"ticket_number": ticket.ticket_number, "priority": priority.name.value},
        )
        self.db.commit()

        self.notification_service.queue_notification(
            background_tasks,
            user_id=current_user.id,
            notif_type=NotificationType.TICKET_CREATED,
            message=f"Your ticket {ticket.ticket_number} has been created.",
            ticket_id=ticket.id,
        )
        return self.ticket_repo.get_by_id(ticket.id)

    # ---------- read ----------

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
        date_from: datetime | None,
        date_to: datetime | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[Ticket], int]:
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

    # ---------- update ----------

    def update_ticket(
        self, current_user: User, ticket_id: uuid.UUID, data: UpdateTicketRequest
    ) -> Ticket:
        ticket = self.get_ticket(current_user, ticket_id)

        if ticket.status == TicketStatus.CLOSED:
            raise BadRequestException("Closed tickets cannot be modified", "TICKET_CLOSED")

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
        self,
        current_user: User,
        ticket_id: uuid.UUID,
        new_status: TicketStatus,
        background_tasks: BackgroundTasks,
        ip_address: str | None = None,
    ) -> Ticket:
        ticket = self.get_ticket(current_user, ticket_id)

        if current_user.role == UserRole.CUSTOMER:
            raise ForbiddenException("Customers cannot change ticket status", "INSUFFICIENT_ROLE")

        current_status = ticket.status
        allowed_next = VALID_STATUS_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_next:
            raise BadRequestException(
                f"Cannot move ticket from {current_status.value} to {new_status.value}",
                "INVALID_STATUS_TRANSITION",
            )

        raw = self.ticket_repo.get_raw_by_id(ticket_id)
        raw.status = new_status

        self.ticket_repo.record_history(
            ticket_id=raw.id,
            changed_by_id=current_user.id,
            old_status=current_status,
            new_status=new_status,
        )
        self.audit_service.log(
            action=AuditAction.STATUS_CHANGED,
            entity="ticket",
            entity_id=str(ticket_id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata={"old_status": current_status.value, "new_status": new_status.value},
        )
        if new_status == TicketStatus.CLOSED:
            self.audit_service.log(
                action=AuditAction.TICKET_CLOSED,
                entity="ticket",
                entity_id=str(ticket_id),
                user_id=current_user.id,
                ip_address=ip_address,
            )
        self.db.commit()

        notif_type = {
            TicketStatus.RESOLVED: NotificationType.TICKET_RESOLVED,
            TicketStatus.CLOSED: NotificationType.TICKET_CLOSED,
        }.get(new_status, NotificationType.STATUS_CHANGED)

        self.notification_service.queue_notification(
            background_tasks,
            user_id=raw.customer_id,
            notif_type=notif_type,
            message=f"Ticket {raw.ticket_number} status changed to {new_status.value}.",
            ticket_id=raw.id,
        )
        return self.ticket_repo.get_by_id(ticket_id)

    def assign_ticket(
        self,
        current_user: User,
        ticket_id: uuid.UUID,
        agent_id: uuid.UUID,
        background_tasks: BackgroundTasks,
        ip_address: str | None = None,
    ) -> Ticket:
        if current_user.role == UserRole.CUSTOMER:
            raise ForbiddenException("Customers cannot assign tickets", "INSUFFICIENT_ROLE")

        raw = self.ticket_repo.get_raw_by_id(ticket_id)
        if raw is None:
            raise NotFoundException("Ticket not found", "TICKET_NOT_FOUND")

        agent = self.user_repo.get_by_id(agent_id)
        if agent is None or agent.role != UserRole.AGENT:
            raise NotFoundException("Agent not found", "AGENT_NOT_FOUND")
        if not agent.is_active:
            raise BadRequestException("Inactive agents cannot receive tickets", "AGENT_INACTIVE")

        old_agent_id = raw.assigned_agent_id
        raw.assigned_agent_id = agent.id

        self.ticket_repo.record_history(
            ticket_id=raw.id,
            changed_by_id=current_user.id,
            old_agent_id=old_agent_id,
            new_agent_id=agent.id,
        )
        self.audit_service.log(
            action=AuditAction.TICKET_ASSIGNED,
            entity="ticket",
            entity_id=str(raw.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata={"agent_id": str(agent.id)},
        )
        self.db.commit()

        notif_type = (
            NotificationType.TICKET_REASSIGNED if old_agent_id else NotificationType.TICKET_ASSIGNED
        )
        self.notification_service.queue_notification(
            background_tasks,
            user_id=agent.id,
            notif_type=notif_type,
            message=f"You have been assigned ticket {raw.ticket_number}.",
            ticket_id=raw.id,
        )
        return self.ticket_repo.get_by_id(ticket_id)

    # ---------- delete ----------

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
        raise ForbiddenException("You do not have access to this ticket", "TICKET_ACCESS_DENIED")