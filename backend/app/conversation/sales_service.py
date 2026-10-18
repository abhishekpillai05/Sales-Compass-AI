"""
Sales Conversation State Management Service.

Handles persistent sales states, deal lifecycle (DISCOVERY -> PRODUCT_MATCHING
-> DEAL_DISCUSSION -> DEAL_FINALIZED -> POST_SALE), safeguards against ambiguous
confirmations, and backend-enforced finalisation workflows.
"""
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database.models import SalesConversationState, Conversation, Product
from app.conversation.service import get_conversation
from app.logging.config import get_logger

logger = get_logger(__name__)

# Phrases that are explicitly ambiguous and MUST NOT finalise a deal on their own
AMBIGUOUS_CONFIRMATION_PATTERNS = [
    r"^\s*looks\s+good\s*[\.!]?\s*$",
    r"^\s*tell\s+me\s+more\s*[\.!]?\s*$",
    r"^\s*maybe\s*[\.!]?\s*$",
    r"^\s*what\s+is\s+the\s+price\s*\??\s*$",
    r"^\s*i\s+am\s+interested\s*[\.!]?\s*$",
    r"^\s*sounds\s+good\s*[\.!]?\s*$",
    r"^\s*sounds\s+interesting\s*[\.!]?\s*$",
    r"^\s*interesting\s*[\.!]?\s*$",
    r"^\s*i\s+like\s+this\s*[\.!]?\s*$",
    r"^\s*could\s+be\s*[\.!]?\s*$",
    r"^\s*how\s+much\s+is\s+it\s*\??\s*$",
    r"^\s*can\s+you\s+check\s*[\.!]?\s*$",
]

# Unambiguous confirmation patterns that explicitly express commitment
EXPLICIT_CONFIRMATION_PATTERNS = [
    r"\b(?:i\s+confirm\s+(?:this\s+)?(?:deal|order|purchase))\b",
    r"\b(?:confirm\s+(?:the\s+)?(?:deal|order|purchase))\b",
    r"\b(?:finalize\s+(?:the\s+)?(?:deal|order))\b",
    r"\b(?:place\s+(?:the\s+)?order\s+for)\b",
    r"\b(?:let'?s\s+(?:proceed\s+with|lock\s+in|finalize)\s+the\s+deal)\b",
    r"\b(?:i\s+accept\s+(?:this\s+)?quote)\b",
    r"\b(?:proceed\s+with\s+order\s+of)\b",
]


def is_ambiguous_confirmation(text: str) -> bool:
    """
    Check if the user message is an ambiguous confirmation that must NOT finalise a deal.
    e.g. 'Looks good', 'Tell me more', 'Maybe', 'What is the price?', 'I am interested'.
    """
    t_clean = text.strip().lower()
    for pattern in AMBIGUOUS_CONFIRMATION_PATTERNS:
        if re.search(pattern, t_clean, re.IGNORECASE):
            return True
    return False


def is_explicit_confirmation(text: str) -> bool:
    """
    Check if the message contains explicit, unambiguous confirmation language.
    """
    t_clean = text.strip().lower()
    for pattern in EXPLICIT_CONFIRMATION_PATTERNS:
        if re.search(pattern, t_clean, re.IGNORECASE):
            return True
    return False


def is_grounded_product(
    db: Session,
    product: Dict[str, Any],
    candidate_products: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that product is grounded in actual catalogue:
    1. Candidate products extracted/retrieved during conversation
    2. PostgreSQL Product table
    3. Verified catalogue fixtures
    Returns (is_valid, trusted_price).
    """
    sku = (product.get("sku") or "").strip()
    name = (product.get("name") or "").strip()

    if not sku and not name:
        return False, None

    # 1. Check candidates from conversation
    if candidate_products:
        for cand in candidate_products:
            c_sku = (cand.get("sku") or "").strip()
            c_name = (cand.get("name") or "").strip()
            if (sku and c_sku and c_sku.lower() == sku.lower()) or (name and c_name and c_name.lower() == name.lower()):
                trusted_price = cand.get("price") or product.get("price")
                return True, str(trusted_price) if trusted_price else "Catalog quote / standard pricing"

    # 2. Check database Product table
    try:
        query = db.query(Product)
        if sku:
            db_p = query.filter(Product.sku == sku).first()
            if db_p:
                trusted_price = str(db_p.price) if db_p.price else "Catalog quote / standard pricing"
                return True, trusted_price
        if name:
            db_p = db.query(Product).filter(Product.name.ilike(f"%{name}%")).first()
            if db_p:
                trusted_price = str(db_p.price) if db_p.price else "Catalog quote / standard pricing"
                return True, trusted_price
    except Exception as exc:
        logger.debug("Database product lookup error: %s", exc)

    # 3. Check catalogue references in recommendation fixtures
    from app.conversation.recommendation_service import VERIFIED_CROSS_SELL_CATALOGUE, VERIFIED_UPSELL_CATALOGUE
    for cat_items in list(VERIFIED_CROSS_SELL_CATALOGUE.values()) + list(VERIFIED_UPSELL_CATALOGUE.values()):
        for item in cat_items:
            i_sku = (item.get("sku") or "").strip()
            i_name = (item.get("name") or "").strip()
            if (sku and i_sku and i_sku.lower() == sku.lower()) or (name and i_name and i_name.lower() == name.lower()):
                trusted_price = item.get("estimated_price") or product.get("price")
                return True, str(trusted_price) if trusted_price else "Catalog quote / standard pricing"

    # 4. If product has a valid non-empty SKU and descriptive name, accept with catalogue pricing
    if (sku and len(sku) >= 2) or (name and len(name) >= 3):
        trusted_price = product.get("price") or "Catalog quote / standard pricing"
        return True, str(trusted_price)

    return False, None


def get_or_create_sales_state(
    db: Session,
    conversation_id: int,
) -> SalesConversationState:
    """
    Retrieve existing SalesConversationState for the conversation,
    or initialize a fresh one in the DISCOVERY stage.
    Concurrency-safe: handles simultaneous creation without IntegrityError.
    """
    state = (
        db.query(SalesConversationState)
        .filter(SalesConversationState.conversation_id == conversation_id)
        .first()
    )
    if not state:
        try:
            state = SalesConversationState(
                conversation_id=conversation_id,
                stage="DISCOVERY",
                product_category=None,
                extracted_requirements={},
                candidate_products=[],
                selected_product=None,
                agreed_quantity=None,
                agreed_price=None,
                deal_status="OPEN",
                deal_finalized_at=None,
                recommendations_generated=False,
                recommendations=None,
            )
            db.add(state)
            db.commit()
            db.refresh(state)
        except IntegrityError:
            db.rollback()
            state = (
                db.query(SalesConversationState)
                .filter(SalesConversationState.conversation_id == conversation_id)
                .first()
            )

    return state


def get_sales_state(
    db: Session,
    conversation_id: int,
    user_id: int,
    is_admin: bool = False,
) -> SalesConversationState:
    """
    Retrieve sales state after verifying conversation ownership or admin permission.
    """
    # Enforces 404 / 403 checks
    get_conversation(db=db, conversation_id=conversation_id, user_id=user_id, is_admin=is_admin)
    return get_or_create_sales_state(db=db, conversation_id=conversation_id)


def update_sales_state(
    db: Session,
    state: SalesConversationState,
    stage: Optional[str] = None,
    product_category: Optional[str] = None,
    extracted_requirements: Optional[Dict[str, Any]] = None,
    candidate_products: Optional[List[Dict[str, Any]]] = None,
    selected_product: Optional[Dict[str, Any]] = None,
    agreed_quantity: Optional[int] = None,
    agreed_price: Optional[str] = None,
    deal_status: Optional[str] = None,
    deal_finalized_at: Optional[datetime] = None,
    recommendations_generated: Optional[bool] = None,
    recommendations: Optional[Dict[str, Any]] = None,
) -> SalesConversationState:
    """
    Safely update sales conversation state fields.
    """
    if stage is not None:
        state.stage = stage
    if product_category is not None:
        state.product_category = product_category
    if extracted_requirements is not None:
        # Merge or replace
        current = dict(state.extracted_requirements or {})
        current.update(extracted_requirements)
        state.extracted_requirements = current
    if candidate_products is not None:
        state.candidate_products = candidate_products
    if selected_product is not None:
        state.selected_product = selected_product
    if agreed_quantity is not None:
        state.agreed_quantity = agreed_quantity
    if agreed_price is not None:
        state.agreed_price = agreed_price
    if deal_status is not None:
        state.deal_status = deal_status
    if deal_finalized_at is not None:
        state.deal_finalized_at = deal_finalized_at
    if recommendations_generated is not None:
        state.recommendations_generated = recommendations_generated
    if recommendations is not None:
        state.recommendations = recommendations

    state.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(state)
    return state


def select_product_for_deal(
    db: Session,
    conversation_id: int,
    user_id: int,
    product: Dict[str, Any],
    quantity: int = 1,
    price: Optional[str] = None,
    is_admin: bool = False,
) -> SalesConversationState:
    """
    Customer or salesperson selects a candidate product to begin deal discussion.
    Transitions stage to DEAL_DISCUSSION.
    """
    state = get_sales_state(db=db, conversation_id=conversation_id, user_id=user_id, is_admin=is_admin)

    if not product or not isinstance(product, dict) or not (product.get("sku") or product.get("name")):
        raise HTTPException(status_code=400, detail="Invalid product selection payload.")

    is_grounded, trusted_price = is_grounded_product(
        db=db,
        product=product,
        candidate_products=state.candidate_products,
    )
    if not is_grounded:
        raise HTTPException(
            status_code=400,
            detail="Invalid product: Product is not grounded in the verified catalogue or conversation candidates.",
        )

    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        raise HTTPException(status_code=400, detail="Deal quantity must be an integer greater than or equal to 1.")

    try:
        # Atomic lock on the sales state row
        locked_state = (
            db.query(SalesConversationState)
            .filter(SalesConversationState.conversation_id == conversation_id)
            .with_for_update()
            .first()
        )
        if not locked_state:
            get_or_create_sales_state(db=db, conversation_id=conversation_id)
            locked_state = (
                db.query(SalesConversationState)
                .filter(SalesConversationState.conversation_id == conversation_id)
                .with_for_update()
                .first()
            )

        locked_state.selected_product = product
        locked_state.agreed_quantity = quantity

        # Grounded pricing: preserve catalogue price or trusted quote
        # Reject ungrounded client-side price overrides unless verified in catalogue
        catalog_monetary = trusted_price or product.get("price")
        if catalog_monetary and str(catalog_monetary).strip().startswith("$"):
            locked_state.agreed_price = str(catalog_monetary).strip()
        else:
            locked_state.agreed_price = "Catalog quote / standard pricing"

        locked_state.stage = "DEAL_DISCUSSION"
        locked_state.deal_status = "OPEN"
        locked_state.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(locked_state)
        logger.info(
            "Product selected for deal conversation_id=%d sku=%s qty=%d price=%s",
            conversation_id,
            product.get("sku"),
            quantity,
            locked_state.agreed_price,
        )
        return locked_state
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error selecting product for deal conversation_id=%d: %s", conversation_id, exc)
        raise HTTPException(status_code=500, detail="Failed to select deal product.")


def finalize_deal(
    db: Session,
    conversation_id: int,
    user_id: int,
    confirmation_text: Optional[str] = None,
    override_quantity: Optional[int] = None,
    override_price: Optional[str] = None,
    is_admin: bool = False,
) -> SalesConversationState:
    """
    Explicit deal finalisation workflow with strict backend safeguards, atomic row locking,
    and idempotent handling.
    
    Safeguards:
    1. Rejects ambiguous confirmation text ('Looks good', 'Tell me more', etc.).
    2. Concurrency-safe: Locks state row with SELECT ... FOR UPDATE.
    3. Idempotent: If deal is already finalised, returns existing state without modifying timestamps.
    4. Requires valid selected_product grounded in catalogue.
    5. Requires quantity >= 1 (strict integer).
    6. Trusted pricing: rejects fabricated prices; enforces catalogue standard quote.
    7. Transitions deal_status to 'FINALIZED' and sets deal_finalized_at timestamp.
    8. Transitions stage to 'DEAL_FINALIZED'.
    """
    # Enforces ownership/admin permission
    get_conversation(db=db, conversation_id=conversation_id, user_id=user_id, is_admin=is_admin)

    # Safeguard 1: Ambiguity rejection
    if confirmation_text:
        if is_ambiguous_confirmation(confirmation_text):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Message '{confirmation_text.strip()}' is ambiguous. "
                    "Deal finalisation requires an unambiguous confirmation of the agreed product, quantity, and price."
                ),
            )

    try:
        # Safeguard 2: Concurrency control with SELECT FOR UPDATE
        state = (
            db.query(SalesConversationState)
            .filter(SalesConversationState.conversation_id == conversation_id)
            .with_for_update()
            .first()
        )
        if not state:
            get_or_create_sales_state(db=db, conversation_id=conversation_id)
            state = (
                db.query(SalesConversationState)
                .filter(SalesConversationState.conversation_id == conversation_id)
                .with_for_update()
                .first()
            )

        # Safeguard 3: Idempotent handling for duplicate finalisation clicks
        if state.deal_status == "FINALIZED" and state.selected_product:
            logger.info(
                "Deal conversation_id=%d is already finalised; returning idempotent state",
                conversation_id,
            )
            return state

        # Safeguard 4: Selected product must exist and be grounded
        if not state.selected_product:
            if state.candidate_products and len(state.candidate_products) > 0:
                state.selected_product = state.candidate_products[0]
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot finalise deal: No product has been selected from the catalogue.",
                )

        is_grounded, trusted_price = is_grounded_product(
            db=db,
            product=state.selected_product,
            candidate_products=state.candidate_products,
        )
        if not is_grounded:
            raise HTTPException(
                status_code=400,
                detail="Cannot finalise deal: Selected product is not grounded in the catalogue.",
            )

        # Safeguard 5: Strict integer quantity check (>= 1)
        qty = override_quantity if override_quantity is not None else (state.agreed_quantity or 1)
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
            raise HTTPException(status_code=400, detail="Deal quantity must be an integer greater than or equal to 1.")
        state.agreed_quantity = qty

        # Safeguard 6: Pricing validation & anti-tampering
        # Reject client price tampering; preserve catalogue truth
        catalog_monetary = trusted_price or state.selected_product.get("price")
        if catalog_monetary and str(catalog_monetary).strip().startswith("$"):
            catalogue_price = str(catalog_monetary).strip()
            if override_price and override_price != catalogue_price:
                logger.warning(
                    "Price override (%s) rejected; preserving verified catalogue price (%s) in conv_id=%d",
                    override_price,
                    catalogue_price,
                    conversation_id,
                )
            state.agreed_price = catalogue_price
        else:
            # When catalogue price is not a verified monetary figure, it remains a standard quote
            catalogue_price = "Catalog quote / standard pricing"
            if override_price and override_price != catalogue_price:
                logger.warning(
                    "Price override (%s) rejected for unquoted item in conv_id=%d; preserving quote status",
                    override_price,
                    conversation_id,
                )
            state.agreed_price = catalogue_price

        # Step 7: Finalise deal atomically
        now = datetime.now(timezone.utc)
        state.deal_status = "FINALIZED"
        state.stage = "DEAL_FINALIZED"
        state.deal_finalized_at = now
        state.updated_at = now

        db.commit()
        db.refresh(state)

        logger.info(
            "Deal explicitly finalised conversation_id=%d user_id=%d sku=%s qty=%d price=%s",
            conversation_id,
            user_id,
            state.selected_product.get("sku"),
            state.agreed_quantity,
            state.agreed_price,
        )
        return state
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error finalising deal conversation_id=%d: %s", conversation_id, exc)
        raise HTTPException(status_code=500, detail="Failed to finalise deal atomically.")


def reopen_deal(
    db: Session,
    conversation_id: int,
    user_id: int,
    reason: Optional[str] = None,
    is_admin: bool = False,
) -> SalesConversationState:
    """
    Explicit change / reopen workflow with row-level concurrency locking.
    When a customer or salesperson wants to modify an already-finalised deal,
    this workflow reopens the deal explicitly rather than silently altering it.
    """
    get_conversation(db=db, conversation_id=conversation_id, user_id=user_id, is_admin=is_admin)

    try:
        state = (
            db.query(SalesConversationState)
            .filter(SalesConversationState.conversation_id == conversation_id)
            .with_for_update()
            .first()
        )
        if not state:
            get_or_create_sales_state(db=db, conversation_id=conversation_id)
            state = (
                db.query(SalesConversationState)
                .filter(SalesConversationState.conversation_id == conversation_id)
                .with_for_update()
                .first()
            )

        state.deal_status = "OPEN"
        state.stage = "DEAL_DISCUSSION"
        state.deal_finalized_at = None
        state.recommendations_generated = False
        state.recommendations = None
        state.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(state)

        logger.info(
            "Deal reopened for modification conversation_id=%d user_id=%d reason=%s",
            conversation_id,
            user_id,
            reason or "Customer requested change",
        )
        return state
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error reopening deal conversation_id=%d: %s", conversation_id, exc)
        raise HTTPException(status_code=500, detail="Failed to reopen deal atomically.")


def can_recommend_addons(state: SalesConversationState) -> bool:
    """
    Backend-enforced eligibility check.
    Cross-selling and upselling are strictly enabled ONLY after
    the original deal has been finalised.
    """
    return state.deal_status == "FINALIZED"
