import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.enums import TicketPriority, TicketStatus
from app.models.user import User
from app.schemas.ticket import (
    CreateTicketRequest,
    PaginatedTickets,
    TicketResponse,
    UpdateStatusRequest,
    UpdateTicketRequest,
)
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: CreateTicketRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    return service.create_ticket(current_user, data)


@router.get("", response_model=PaginatedTickets)
def list_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status_: TicketStatus | None = Query(default=None, alias="status"),
    priority: TicketPriority | None = None,
    category_id: uuid.UUID | None = None,
    assigned_agent: uuid.UUID | None = Query(default=None, alias="assigned_agent"),
    customer: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    items, total = service.list_tickets(
        current_user=current_user,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_,
        priority_filter=priority,
        category_id=category_id,
        assigned_agent_id=assigned_agent,
        customer_id=customer,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedTickets(
        items=[TicketResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    return service.get_ticket(current_user, ticket_id)


@router.patch("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: uuid.UUID,
    data: UpdateTicketRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    return service.update_ticket(current_user, ticket_id, data)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_status(
    ticket_id: uuid.UUID,
    data: UpdateStatusRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    return service.update_status(current_user, ticket_id, data.status)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    service.delete_ticket(current_user, ticket_id)