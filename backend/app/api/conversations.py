"""
Conversation Management API endpoints.

GET  /conversations                  -- List current user's conversations
GET  /conversations/{conversation_id} -- Retrieve conversation messages
DELETE /conversations/{conversation_id} -- Delete conversation and its messages
PATCH /conversations/{conversation_id} -- Rename conversation
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.roles import UserRole
from app.database.models import User
from app.database.session import SessionLocal
from app.logging.config import get_logger


def is_authorized_admin(user: User) -> bool:
    """Verify strictly if the user has canonical ADMIN role, preventing legacy role leakage."""
    return UserRole.normalize(getattr(user, "role", None)) == UserRole.ADMIN.value
from app.conversation.service import (
    list_conversations,
    get_conversation,
    get_conversation_messages,
    delete_conversation,
    update_conversation_title,
)
from app.conversation.sales_service import (
    get_sales_state,
    select_product_for_deal,
    finalize_deal,
    reopen_deal,
    can_recommend_addons,
)
from app.conversation.recommendation_service import generate_recommendations
from app.generation.api_schemas import SalesStateResponse

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


def format_sales_state(state) -> SalesStateResponse:
    return SalesStateResponse(
        stage=state.stage,
        product_category=state.product_category,
        extracted_requirements=state.extracted_requirements or {},
        candidate_products=state.candidate_products or [],
        selected_product=state.selected_product,
        agreed_quantity=state.agreed_quantity,
        agreed_price=state.agreed_price,
        deal_status=state.deal_status,
        deal_finalized_at=state.deal_finalized_at,
        can_recommend_addons=can_recommend_addons(state),
        recommendations=state.recommendations,
    )


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
    sales_state: Optional[SalesStateResponse] = None


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class SelectProductRequest(BaseModel):
    product: Dict[str, Any]
    quantity: int = Field(default=1, ge=1)
    price: Optional[str] = None


class ConfirmDealRequest(BaseModel):
    confirmation_text: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=1)
    price: Optional[str] = None


class ReopenDealRequest(BaseModel):
    reason: Optional[str] = None



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
    is_admin = is_authorized_admin(current_user)
    conv = get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        is_admin=is_admin,
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

    sales_state = get_sales_state(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )

    return ConversationDetail(
        id=conv.id,
        title=conv.title or "Untitled Conversation",
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=formatted_messages,
        sales_state=format_sales_state(sales_state),
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


# ── Deal Tracking, Confirmation & Recommendation Endpoints ──────────────────

@router.get(
    "/{conversation_id}/deal",
    response_model=SalesStateResponse,
)
def get_deal_state(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve structured sales and deal tracking state for a conversation."""
    is_admin = is_authorized_admin(current_user)
    state = get_sales_state(db=db, conversation_id=conversation_id, user_id=current_user.id, is_admin=is_admin)
    return format_sales_state(state)


@router.post(
    "/{conversation_id}/deal/select-product",
    response_model=SalesStateResponse,
)
@router.post(
    "/{conversation_id}/deal/select-item",
    response_model=SalesStateResponse,
)
def select_deal_product(
    conversation_id: int,
    request: SelectProductRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Select candidate product to begin deal discussion (stage -> DEAL_DISCUSSION).
    Supports both `/deal/select-product` and `/deal/select-item`.
    """
    is_admin = is_authorized_admin(current_user)
    state = select_product_for_deal(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        product=request.product,
        quantity=request.quantity,
        price=request.price,
        is_admin=is_admin,
    )
    return format_sales_state(state)


@router.post(
    "/{conversation_id}/deal/confirm",
    response_model=SalesStateResponse,
)
def confirm_deal_endpoint(
    conversation_id: int,
    request: Optional[ConfirmDealRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicit deal finalisation endpoint with strict safeguards and atomic row locking.
    Transitions deal_status to FINALIZED and stage to DEAL_FINALIZED.
    """
    if request is None:
        request = ConfirmDealRequest()
    is_admin = is_authorized_admin(current_user)
    state = finalize_deal(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        confirmation_text=request.confirmation_text,
        override_quantity=request.quantity,
        override_price=request.price,
        is_admin=is_admin,
    )
    return format_sales_state(state)


@router.post(
    "/{conversation_id}/deal/recommendations",
    response_model=Dict[str, Any],
)
@router.post(
    "/{conversation_id}/deal/recs",
    response_model=Dict[str, Any],
)
def get_recommendations_endpoint(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate cross-selling and upselling recommendations.
    STRICT BACKEND SAFEGUARD: Only permitted when deal_status == 'FINALIZED'.
    Supports both `/deal/recommendations` and `/deal/recs`.
    """
    is_admin = is_authorized_admin(current_user)
    state = get_sales_state(db=db, conversation_id=conversation_id, user_id=current_user.id, is_admin=is_admin)
    return generate_recommendations(db=db, state=state)


@router.post(
    "/{conversation_id}/deal/reopen",
    response_model=SalesStateResponse,
)
def reopen_deal_endpoint(
    conversation_id: int,
    request: Optional[ReopenDealRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicit deal modification / reopen workflow.
    Reopens deal for modification without silently altering finalised terms.
    """
    if request is None:
        request = ReopenDealRequest()
    is_admin = is_authorized_admin(current_user)
    state = reopen_deal(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        reason=request.reason,
        is_admin=is_admin,
    )
    return format_sales_state(state)

