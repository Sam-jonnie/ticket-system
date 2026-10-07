import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TicketPriority, TicketStatus


class CreateTicketRequest(BaseModel):

    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10)
    category_id: uuid.UUID
    priority_name: TicketPriority

    model_config = ConfigDict(str_strip_whitespace=True)


class UpdateTicketRequest(BaseModel):

    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10)
    category_id: uuid.UUID | None = None
    priority_name: TicketPriority | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class UpdateStatusRequest(BaseModel):
    status: TicketStatus


class AssignTicketRequest(BaseModel):
    agent_id: uuid.UUID


class UserSummary(BaseModel):
    id: uuid.UUID
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class CategorySummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class PrioritySummary(BaseModel):
    id: uuid.UUID
    name: TicketPriority
    sla_hours: int

    model_config = ConfigDict(from_attributes=True)


class TicketResponse(BaseModel):
    id: uuid.UUID
    ticket_number: str
    title: str
    description: str
    status: TicketStatus
    customer: UserSummary
    assigned_agent: UserSummary | None
    category: CategorySummary
    priority: PrioritySummary
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedTickets(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    page_size: int