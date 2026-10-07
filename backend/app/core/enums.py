from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    AGENT = "agent"
    CUSTOMER = "customer"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


VALID_STATUS_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.OPEN},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.IN_PROGRESS},  # reopen = back to IN_PROGRESS
    TicketStatus.CLOSED: set(),  # terminal state — no transitions out
}

class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(StrEnum):
    TICKET_CREATED = "ticket_created"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_REASSIGNED = "ticket_reassigned"
    STATUS_CHANGED = "status_changed"
    NEW_COMMENT = "new_comment"
    TICKET_RESOLVED = "ticket_resolved"
    TICKET_CLOSED = "ticket_closed"
    SLA_BREACHED = "sla_breached"


class AuditAction(StrEnum):
    LOGIN = "login"
    FAILED_LOGIN = "failed_login"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_ASSIGNED = "ticket_assigned"
    STATUS_CHANGED = "status_changed"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_UPLOADED = "attachment_uploaded"
    TICKET_CLOSED = "ticket_closed"

