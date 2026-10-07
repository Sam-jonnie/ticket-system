# app/services/attachment_service.py
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.ticket_attachment import TicketAttachment
from app.models.user import User
from app.core.enums import UserRole
from app.repositories.attachment_repository import AttachmentRepository
from app.services.ticket_service import TicketService
from app.utils.file_storage import delete_file, save_file
from app.utils.file_validation import validate_attachment


class AttachmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AttachmentRepository(db)
        self.ticket_service = TicketService(db)

    def upload_attachment(
        self,
        current_user: User,
        ticket_id: uuid.UUID,
        file_bytes: bytes,
        original_filename: str,
    ) -> TicketAttachment:
        ticket = self.ticket_service.get_ticket(current_user, ticket_id)  # 404/403 as needed

        try:
            detected_mime_type = validate_attachment(file_bytes, original_filename)
        except ValueError as exc:
            raise BadRequestException(str(exc), "INVALID_ATTACHMENT")

        storage_path = save_file(file_bytes, ticket.id, original_filename)

        attachment = TicketAttachment(
            ticket_id=ticket.id,
            uploaded_by_id=current_user.id,
            file_name=original_filename,
            file_type=detected_mime_type,
            file_size=len(file_bytes),
            storage_path=storage_path,
        )
        self.repo.create(attachment)
        self.db.commit()
        attachment.uploaded_by = current_user
        return attachment

    def list_attachments(self, current_user: User, ticket_id: uuid.UUID) -> list[TicketAttachment]:
        self.ticket_service.get_ticket(current_user, ticket_id)  # access check
        rows = self.repo.list_for_ticket(ticket_id)
        result = []
        for attachment, uploader in rows:
            attachment.uploaded_by = uploader
            result.append(attachment)
        return result

    def get_attachment_for_download(
        self, current_user: User, attachment_id: uuid.UUID
    ) -> TicketAttachment:
        attachment = self.repo.get_by_id(attachment_id)
        if attachment is None:
            raise NotFoundException("Attachment not found", "ATTACHMENT_NOT_FOUND")
        self.ticket_service.get_ticket(current_user, attachment.ticket_id)  # access check
        return attachment

    def delete_attachment(self, current_user: User, attachment_id: uuid.UUID) -> None:
        attachment = self.repo.get_by_id(attachment_id)
        if attachment is None:
            raise NotFoundException("Attachment not found", "ATTACHMENT_NOT_FOUND")

        # Access to the ticket first...
        self.ticket_service.get_ticket(current_user, attachment.ticket_id)

        # ...then ownership: uploader or admin only (mirrors the comment-moderation rule)
        if current_user.role != UserRole.ADMIN and attachment.uploaded_by_id != current_user.id:
            raise ForbiddenException(
                "You can only delete your own attachments", "ATTACHMENT_ACCESS_DENIED"
            )

        delete_file(attachment.storage_path)
        self.repo.delete(attachment)
        self.db.commit()