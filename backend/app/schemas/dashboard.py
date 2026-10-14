import uuid

from pydantic import BaseModel


class TicketStats(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    overdue_tickets: int
    critical_tickets: int


class AgentTicketCount(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    ticket_count: int


class AdminStats(BaseModel):
    total_customers: int
    total_agents: int
    active_agents: int
    tickets_per_agent: list[AgentTicketCount]


class AgentStats(BaseModel):
    my_open_tickets: int
    my_overdue_tickets: int
    my_resolved_tickets: int