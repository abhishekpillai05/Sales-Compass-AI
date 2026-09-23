"""
Conversation Management API endpoints.

GET  /conversations                  -- List current user's conversations
GET  /conversations/{conversation_id} -- Retrieve conversation messages
DELETE /conversations/{conversation_id} -- Delete conversation and its messages
PATCH /conversations/{conversation_id} -- Rename conversation
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.models import User
from app.database.session import SessionLocal
from app.logging.config import get_logger
from app.conversation.service import (
    list_conversations,
    get_conversation,
    get_conversation_messages,
    delete_conversation,
    update_conversation_title,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class ConversationSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageItem(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[list] = None
    created_at: datetime


class ConversationDetail(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageItem]


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[ConversationSummary],
)
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all conversations owned by the authenticated user, newest updated first."""
    return list_conversations(db=db, user_id=current_user.id)


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
)
def get_conversation_by_id(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all messages in a specific conversation.
    Enforces user ownership (403 if belonging to another user, 404 if not found).
    """
    conv = get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    messages = get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    formatted_messages = [
        MessageItem(
            id=m.id,
            role=m.role,
            content=m.content,
            sources=m.sources,
            created_at=m.created_at,
        )
        for m in messages
    ]

    return ConversationDetail(
        id=conv.id,
        title=conv.title or "Untitled Conversation",
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=formatted_messages,
    )


@router.delete(
    "/{conversation_id}",
)
def delete_conversation_by_id(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages. Enforces ownership."""
    delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    logger.info(
        "conversation deleted user_id=%d conversation_id=%d",
        current_user.id,
        conversation_id,
    )
    return {"message": "Conversation deleted successfully."}


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummary,
)
def rename_conversation(
    conversation_id: int,
    request: RenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename a conversation. Enforces ownership."""
    conv = update_conversation_title(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        title=request.title,
    )
    messages = get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(messages),
    )
