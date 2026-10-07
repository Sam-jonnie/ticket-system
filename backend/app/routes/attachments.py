import uuid

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services.attachment_service import AttachmentService

router = APIRouter(tags=["Attachments"])


def get_attachment_service(db: Session = Depends(get_db)) -> AttachmentService:
    return AttachmentService(db)


@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    ticket_id: uuid.UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
):
    file_bytes = await file.read()
    return service.upload_attachment(current_user, ticket_id, file_bytes, file.filename)


@router.get("/tickets/{ticket_id}/attachments", response_model=list[AttachmentResponse])
def list_attachments(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
):
    return service.list_attachments(current_user, ticket_id)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
):
    attachment = service.get_attachment_for_download(current_user, attachment_id)
    return FileResponse(
        path=attachment.storage_path,
        filename=attachment.file_name,
        media_type=attachment.file_type,
    )


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
):
    service.delete_attachment(current_user, attachment_id)