import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.comment import CommentResponse, CreateCommentRequest, UpdateCommentRequest
from app.services.comment_service import CommentService

router = APIRouter(tags=["Comments"])


def get_comment_service(db: Session = Depends(get_db)) -> CommentService:
    return CommentService(db)


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    ticket_id: uuid.UUID,
    data: CreateCommentRequest,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    return service.add_comment(current_user, ticket_id, data.message)


@router.get("/tickets/{ticket_id}/comments", response_model=list[CommentResponse])
def list_comments(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    return service.list_comments(current_user, ticket_id)


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
def update_comment(
    comment_id: uuid.UUID,
    data: UpdateCommentRequest,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    return service.update_comment(current_user, comment_id, data.message)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    service.delete_comment(current_user, comment_id)