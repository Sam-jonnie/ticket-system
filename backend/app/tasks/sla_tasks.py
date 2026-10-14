from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.enums import NotificationType, TicketStatus, UserRole
from app.models.notification import Notification
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User
from app.services.notification_service import email_subject, queue_email

WARNING_THRESHOLD = 0.8        # warn once 80% of the SLA window has elapsed
ESCALATION_GRACE_RATIO = 0.5   # escalate once overdue by 50% of the SLA window


def _already_sent(db: Session, ticket_id, notif_type: NotificationType) -> bool:
    found = db.scalar(
        select(Notification.id)
        .where(Notification.ticket_id == ticket_id, Notification.type == notif_type)
        .limit(1)
    )
    return found is not None


def _notify(
    db: Session,
    user_ids: set,
    notif_type: NotificationType,
    message: str,
    ticket_id,
    outbox: list[tuple[str, str, str]],
) -> None:
    """Adds one notification per ACTIVE recipient and queues their email for after commit."""
    if not user_ids:
        return
    users = db.scalars(select(User).where(User.id.in_(user_ids), User.is_active.is_(True))).all()
    for user in users:
        db.add(
            Notification(user_id=user.id, ticket_id=ticket_id, type=notif_type, message=message)
        )
        outbox.append((user.email, email_subject(notif_type), message))


@celery_app.task(name="app.tasks.sla_tasks.check_sla_breaches")
def check_sla_breaches() -> dict[str, int]:
    """Scheduled by Celery Beat. Runs the warning / breach / escalation checks."""
    db = SessionLocal()
    counts = {"warnings": 0, "breaches": 0, "escalations": 0}
    outbox: list[tuple[str, str, str]] = []
    try:
        now = datetime.now(timezone.utc)

        open_tickets = db.execute(
            select(Ticket, Priority)
            .join(Priority, Ticket.priority_id == Priority.id)
            .where(
                Ticket.due_date.is_not(None),
                Ticket.status.not_in([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
            )
        ).all()

        admin_ids = set(
            db.scalars(
                select(User.id).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
            ).all()
        )

        for ticket, priority in open_tickets:
            sla_window = timedelta(hours=priority.sla_hours)
            window_start = ticket.due_date - sla_window
            elapsed_ratio = (now - window_start) / sla_window  # timedelta / timedelta = float

            if now > ticket.due_date:
                # --- stage 2: breach ---
                if not _already_sent(db, ticket.id, NotificationType.SLA_BREACHED):
                    recipients = {ticket.customer_id}
                    if ticket.assigned_agent_id:
                        recipients.add(ticket.assigned_agent_id)
                    _notify(
                        db, recipients, NotificationType.SLA_BREACHED,
                        f"SLA breached for ticket {ticket.ticket_number}.",
                        ticket.id, outbox,
                    )
                    counts["breaches"] += 1

                # --- stage 3: escalation to admins ---
                escalate_after = ticket.due_date + sla_window * ESCALATION_GRACE_RATIO
                if now > escalate_after and not _already_sent(
                    db, ticket.id, NotificationType.SLA_ESCALATED
                ):
                    _notify(
                        db, admin_ids, NotificationType.SLA_ESCALATED,
                        f"ESCALATION: ticket {ticket.ticket_number} is overdue by more than "
                        f"half its SLA window and needs attention.",
                        ticket.id, outbox,
                    )
                    counts["escalations"] += 1

            elif elapsed_ratio >= WARNING_THRESHOLD and not _already_sent(
                db, ticket.id, NotificationType.SLA_WARNING
            ):
                # --- stage 1: warning ---
                recipients = {ticket.assigned_agent_id} if ticket.assigned_agent_id else admin_ids
                _notify(
                    db, recipients, NotificationType.SLA_WARNING,
                    f"SLA warning: ticket {ticket.ticket_number} has used "
                    f"{int(elapsed_ratio * 100)}% of its SLA window.",
                    ticket.id, outbox,
                )
                counts["warnings"] += 1

        db.commit()
    finally:
        db.close()

    # Emails only go out AFTER the commit succeeded
    for to_email, subject, body in outbox:
        queue_email(to_email, subject, body)

    return counts