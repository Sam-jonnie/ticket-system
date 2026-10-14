import logging
import uuid

from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.enums import NotificationType
from app.core.exceptions import NotFoundException
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger(__name__)


def queue_email(to_email: str, subject: str, body: str) -> None:
    """
    Hands the email to Celery. Never raises: if Redis is down or email is
    disabled, the notification itself still exists in the DB, and a failed
    email must never break the request that triggered it.
    """
    from app.core.config import settings

    if not settings.email_enabled:
        return
    try:
        from app.tasks.email_tasks import send_email_task

        send_email_task.delay(to_email, subject, body)
    except Exception:
        logger.exception("Could not queue email to %s", to_email)


def email_subject(notif_type: NotificationType) -> str:
    return f"[Support] {notif_type.value.replace('_', ' ').title()}"


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _create_sync(
        self,
        user_id: uuid.UUID,
        notif_type: NotificationType,
        message: str,
        ticket_id: uuid.UUID | None = None,
    ) -> None:
        """Runs inside BackgroundTasks, after the HTTP response was sent.
        Opens its own session so it doesn't depend on the request's session."""
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            notification = Notification(
                user_id=user_id, ticket_id=ticket_id, type=notif_type, message=message
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)

            user = db.get(User, user_id)
            if user is not None:
                queue_email(user.email, email_subject(notif_type), message)

            try:
                self._push_via_websocket(notification)
            except Exception:
                logger.exception("WebSocket push failed for notification %s", notification.id)
        finally:
            db.close()

    def _push_via_websocket(self, notification: Notification) -> None:
        import asyncio

        from app.core.ws_manager import manager

        asyncio.run(
            manager.send_to_user(
                notification.user_id,
                {
                    "id": str(notification.id),
                    "type": notification.type.value,
                    "message": notification.message,
                    "ticket_id": str(notification.ticket_id) if notification.ticket_id else None,
                },
            )
        )

    def queue_notification(
        self,
        background_tasks: BackgroundTasks,
        user_id: uuid.UUID,
        notif_type: NotificationType,
        message: str,
        ticket_id: uuid.UUID | None = None,
    ) -> None:
        background_tasks.add_task(self._create_sync, user_id, notif_type, message, ticket_id)

    # ---------- read side ----------

    def list_for_user(self, user_id: uuid.UUID, unread_only: bool = False) -> list[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        query = query.order_by(Notification.created_at.desc())
        return list(self.db.scalars(query).all())

    def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
        notification = self.db.get(Notification, notification_id)
        if notification is None or notification.user_id != user_id:
            raise NotFoundException("Notification not found", "NOTIFICATION_NOT_FOUND")
        notification.is_read = True
        self.db.commit()
        return notification

    def mark_all_read(self, user_id: uuid.UUID) -> int:
        result = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        self.db.commit()
        return result.rowcount