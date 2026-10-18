"""
Conversation database service.

Handles conversation lifecycle, message logging, ownership verification,
and retrieval for context-aware chat.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.models import Conversation, ConversationMessage


def create_conversation(
    db: Session,
    user_id: int,
    title: Optional[str] = None,
) -> Conversation:
    """Create a new conversation belonging to the given user."""
    if not title or not title.strip():
        title = "New Conversation"
    else:
        title = title.strip()[:100]

    conversation = Conversation(
        user_id=user_id,
        title=title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(
    db: Session,
    conversation_id: int,
    user_id: int,
    is_admin: bool = False,
) -> Conversation:
    """
    Retrieve a conversation by ID, verifying that it belongs to user_id or user is an admin.

    Raises:
        HTTPException(404): If conversation does not exist.
        HTTPException(403): If conversation belongs to another user and requester is not an admin.
    """
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    if conversation.user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this conversation.",
        )

    return conversation


def list_conversations(
    db: Session,
    user_id: int,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List conversations belonging to the user, ordered by most recently updated."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for conv in conversations:
        msg_count = (
            db.query(func.count(ConversationMessage.id))
            .filter(ConversationMessage.conversation_id == conv.id)
            .scalar()
            or 0
        )
        results.append(
            {
                "id": conv.id,
                "title": conv.title or "Untitled Conversation",
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "message_count": msg_count,
            }
        )

    return results


def get_conversation_messages(
    db: Session,
    conversation_id: int,
    user_id: int,
    limit: int = 100,
) -> List[ConversationMessage]:
    """Retrieve messages for a conversation in chronological order, verifying ownership."""
    get_conversation(db=db, conversation_id=conversation_id, user_id=user_id)

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    return messages


def get_recent_messages(
    db: Session,
    conversation_id: int,
    user_id: int,
    limit: int = 10,
) -> List[ConversationMessage]:
    """Retrieve the most recent messages (up to limit) in chronological order."""
    get_conversation(db=db, conversation_id=conversation_id, user_id=user_id)

    recent_desc = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(recent_desc))


def add_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    sources: Optional[list] = None,
) -> ConversationMessage:
    """Append a new message to the conversation and touch updated_at."""
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid message role '{role}'. Must be 'user' or 'assistant'.")

    message = ConversationMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources,
    )
    db.add(message)

    # Touch conversation updated_at
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if conv:
        conv.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(message)
    return message


def delete_conversation(
    db: Session,
    conversation_id: int,
    user_id: int,
) -> bool:
    """Delete a conversation and all its messages (cascades), verifying ownership."""
    conversation = get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    db.delete(conversation)
    db.commit()
    return True


def update_conversation_title(
    db: Session,
    conversation_id: int,
    user_id: int,
    title: str,
) -> Conversation:
    """Update a conversation title, verifying ownership."""
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty.")

    conversation = get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    conversation.title = title.strip()[:100]
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conversation)
    return conversation
