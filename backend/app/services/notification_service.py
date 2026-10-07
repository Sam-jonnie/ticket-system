# app/services/notification_service.py
import uuid

from fastapi import BackgroundTasks
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.enums import NotificationType
from app.core.exceptions import NotFoundException
from app.models.notification import Notification


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
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            notification = Notification(
                user_id=user_id, ticket_id=ticket_id, type=notif_type, message=message
            )
            db.add(notification)
            db.commit()
        finally:
            db.close()
            
    def queue_notification(
        self,
        background_tasks: BackgroundTasks,
        user_id: uuid.UUID,
        notif_type: NotificationType,
        message: str,
        ticket_id: uuid.UUID | None = None,
    ) -> None:
        """
        Called from within a request's service layer. Doesn't write
        to the DB immediately — schedules the write to happen after
        the response is returned, so creating a ticket doesn't make
        the customer wait on notification-row writes.
        """
        background_tasks.add_task(
            self._create_sync, user_id, notif_type, message, ticket_id
        )

    # ---------- read-side: these run in normal request flow, not background ----------

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