import uuid

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, NotificationType, TicketStatus, UserRole
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.ticket_comment import TicketComment
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.ticket_service import TicketService


class CommentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CommentRepository(db)
        self.ticket_service = TicketService(db)  # reuse its access-check + fetch logic
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)

    def add_comment(
        self,
        current_user: User,
        ticket_id: uuid.UUID,
        message: str,
        background_tasks: BackgroundTasks,
    ) -> TicketComment:
        ticket = self.ticket_service.get_ticket(current_user, ticket_id)  # raises 404/403 as needed

        if ticket.status == TicketStatus.CLOSED:
            raise BadRequestException(
                "Closed tickets cannot receive comments unless reopened", "TICKET_CLOSED"
            )

        comment = TicketComment(ticket_id=ticket.id, user_id=current_user.id, message=message)
        self.repo.create(comment)

        self.audit_service.log(
            action=AuditAction.COMMENT_ADDED,
            entity="ticket",
            entity_id=str(ticket.id),
            user_id=current_user.id,
        )
        self.db.commit()
        comment.user = current_user  # for the response's nested UserSummary

        # Notify the "other side": if the commenter is the customer, notify the
        # assigned agent (if any); if the commenter is agent/admin, notify the customer.
        notify_user_id = (
            ticket.assigned_agent.id
            if current_user.id == ticket.customer.id and ticket.assigned_agent
            else ticket.customer.id
        )
        if notify_user_id != current_user.id:
            self.notification_service.queue_notification(
                background_tasks,
                user_id=notify_user_id,
                notif_type=NotificationType.NEW_COMMENT,
                message=f"New comment on ticket {ticket.ticket_number}.",
                ticket_id=ticket.id,
            )
        return comment

    def list_comments(self, current_user: User, ticket_id: uuid.UUID) -> list[TicketComment]:
        self.ticket_service.get_ticket(current_user, ticket_id)  # access check, result unused
        rows = self.repo.list_for_ticket(ticket_id)
        comments = []
        for comment, user in rows:
            comment.user = user
            comments.append(comment)
        return comments

    def update_comment(
        self, current_user: User, comment_id: uuid.UUID, message: str
    ) -> TicketComment:
        comment = self._get_editable_comment(current_user, comment_id)
        comment.message = message
        self.db.commit()
        comment.user = current_user
        return comment

    def delete_comment(self, current_user: User, comment_id: uuid.UUID) -> None:
        comment = self._get_editable_comment(current_user, comment_id)
        self.db.delete(comment)
        self.db.commit()

    def _get_editable_comment(self, current_user: User, comment_id: uuid.UUID) -> TicketComment:
        comment = self.repo.get_by_id(comment_id)
        if comment is None:
            raise NotFoundException("Comment not found", "COMMENT_NOT_FOUND")

        # Admins can moderate (edit/delete) any comment; everyone else only their own.
        if current_user.role != UserRole.ADMIN and comment.user_id != current_user.id:
            raise ForbiddenException(
                "You can only modify your own comments", "COMMENT_ACCESS_DENIED"
            )
        return comment