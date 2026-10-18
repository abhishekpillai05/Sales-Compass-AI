from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.models import User
from app.database.session import SessionLocal
from app.logging.config import get_logger
from app.logging.query_logger import log_query

from app.retrieval.api_schemas import SearchRequest
from app.retrieval.retriever import retrieve
from app.generation.generator import generate_response
from app.generation.api_schemas import AskResponse, SalesStateResponse

from app.conversation.service import (
    create_conversation,
    get_conversation,
    get_recent_messages,
    add_message,
)
from app.conversation.contextualizer import contextualize_query
from app.conversation.sales_service import (
    get_or_create_sales_state,
    finalize_deal,
    can_recommend_addons,
    is_ambiguous_confirmation,
    is_explicit_confirmation,
)
from app.conversation.sales_extractor import (
    detect_product_category,
    extract_requirements,
    get_next_follow_up_questions,
    has_sufficient_information_for_matching,
)
from app.conversation.recommendation_service import generate_recommendations


logger = get_logger(__name__)

router = APIRouter(
    prefix="/ask",
    tags=["Response Generation"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.post(
    "",
    response_model=AskResponse,
)
def ask(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Step 1: Resolve conversation and fetch prior history if any
        if request.conversation_id is None:
            # Auto-title conversation using first question snippet
            auto_title = request.query.strip()
            if len(auto_title) > 60:
                auto_title = auto_title[:57] + "..."
            conversation = create_conversation(
                db=db,
                user_id=current_user.id,
                title=auto_title,
            )
            conversation_id = conversation.id
            history_messages = []
        else:
            conversation = get_conversation(
                db=db,
                conversation_id=request.conversation_id,
                user_id=current_user.id,
            )
            conversation_id = conversation.id
            history_messages = get_recent_messages(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user.id,
                limit=8,
            )

        # Step 1.1: Resolve persistent SalesConversationState
        sales_state = get_or_create_sales_state(db=db, conversation_id=conversation_id)

        # Step 1.2: Category detection & requirement extraction
        detected_cat = detect_product_category(request.query, sales_state.product_category)
        if detected_cat:
            sales_state.product_category = detected_cat

        updated_reqs, has_req_updates = extract_requirements(
            text=request.query,
            category_id=detected_cat,
            existing_requirements=sales_state.extracted_requirements or {},
        )
        if has_req_updates:
            sales_state.extracted_requirements = updated_reqs

        # Step 1.3: Deal finalisation safeguards & workflow check
        # Ambiguous confirmation ("Looks good", "Tell me more", etc.) MUST NOT finalise deal
        is_ambiguous = is_ambiguous_confirmation(request.query)
        is_explicit = is_explicit_confirmation(request.query)

        if is_explicit and not is_ambiguous:
            if sales_state.selected_product or (sales_state.candidate_products and len(sales_state.candidate_products) > 0):
                try:
                    finalize_deal(
                        db=db,
                        conversation_id=conversation_id,
                        user_id=current_user.id,
                        confirmation_text=request.query,
                    )
                except Exception as exc:
                    logger.warning("Auto deal finalisation skipped: %s", exc)

        # Step 1.4: Update lifecycle stage
        if sales_state.deal_status == "FINALIZED":
            # If recommendations requested or deal is fresh, check recommendations
            if "recommend" in request.query.lower() or "accessory" in request.query.lower() or "upgrade" in request.query.lower():
                try:
                    generate_recommendations(db=db, state=sales_state)
                except Exception as exc:
                    logger.warning("Recommendation generation error: %s", exc)
            if sales_state.recommendations_generated:
                sales_state.stage = "POST_SALE"
            else:
                sales_state.stage = "DEAL_FINALIZED"
        elif sales_state.stage != "DEAL_DISCUSSION":
            # Determine if we have enough info for product matching
            has_enough = has_sufficient_information_for_matching(
                category_id=detected_cat,
                requirements=sales_state.extracted_requirements or {},
            )
            if has_enough:
                sales_state.stage = "PRODUCT_MATCHING"
            else:
                sales_state.stage = "DISCOVERY"

        # Step 1.5: Identify targeted follow-up questions if in DISCOVERY
        suggested_questions: list[str] = []
        if sales_state.stage == "DISCOVERY":
            next_qs = get_next_follow_up_questions(
                category_id=detected_cat,
                current_requirements=sales_state.extracted_requirements or {},
                max_questions=2,
            )
            suggested_questions = [q["question"] for q in next_qs]

        # Step 2: Contextualize user question for Qdrant vector retrieval
        search_query = contextualize_query(
            query=request.query,
            history=history_messages,
        )

        # Step 3: Retrieve relevant chunks
        retrieval_response = retrieve(
            query=search_query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            sku=request.sku,
            category=request.category,
            manufacturer=request.manufacturer,
            document_id=request.document_id,
        )

        # Step 3.1: Extract candidate products from retrieved results
        candidates = []
        seen_skus = set()
        for r in retrieval_response.results:
            sku = (r.metadata or {}).get("sku")
            if sku and sku not in seen_skus:
                seen_skus.add(sku)
                candidates.append({
                    "sku": sku,
                    "name": sku,
                    "category": (r.metadata or {}).get("category"),
                    "manufacturer": (r.metadata or {}).get("manufacturer"),
                    "filename": (r.metadata or {}).get("filename"),
                    "snippet": r.text[:220] if r.text else "",
                })
        if candidates:
            sales_state.candidate_products = candidates
            if not sales_state.selected_product and sales_state.stage in ("PRODUCT_MATCHING", "DEAL_DISCUSSION"):
                sales_state.selected_product = candidates[0]

        # Step 4: Generate final answer with conversation history, retrieved context, and sales guidance
        history_for_llm = [
            {"role": m.role, "content": m.content}
            for m in history_messages
        ]

        sales_guidance = {
            "stage": sales_state.stage,
            "category": sales_state.product_category,
            "extracted_requirements": sales_state.extracted_requirements or {},
            "follow_up_questions": suggested_questions,
            "selected_product": sales_state.selected_product,
            "deal_status": sales_state.deal_status,
            "can_recommend_addons": can_recommend_addons(sales_state),
        }

        response = generate_response(
            query=request.query,
            retrieval_response=retrieval_response,
            conversation_history=history_for_llm,
            sales_guidance=sales_guidance,
        )

        # Step 5: Store original user message and assistant answer in PostgreSQL
        add_message(
            db=db,
            conversation_id=conversation_id,
            role="user",
            content=request.query.strip(),
        )

        add_message(
            db=db,
            conversation_id=conversation_id,
            role="assistant",
            content=response["answer"],
            sources=response.get("sources"),
        )

        # Commit any sales state changes
        db.commit()
        db.refresh(sales_state)

        # Step 6: Log the user's query (Phase 7 query logging — preserved)
        log_query(
            db=db,
            user_id=current_user.id,
            query=request.query,
        )

        logger.info(
            "ask completed user_id=%d conversation_id=%d chunks_retrieved=%d stage=%s",
            current_user.id,
            conversation_id,
            retrieval_response.total_results,
            sales_state.stage,
        )

        sales_state_payload = SalesStateResponse(
            stage=sales_state.stage,
            product_category=sales_state.product_category,
            extracted_requirements=sales_state.extracted_requirements or {},
            candidate_products=sales_state.candidate_products or [],
            selected_product=sales_state.selected_product,
            agreed_quantity=sales_state.agreed_quantity,
            agreed_price=sales_state.agreed_price,
            deal_status=sales_state.deal_status,
            deal_finalized_at=sales_state.deal_finalized_at,
            can_recommend_addons=can_recommend_addons(sales_state),
            recommendations=sales_state.recommendations,
        )

        return AskResponse(
            query=request.query,
            answer=response["answer"],
            conversation_id=conversation_id,
            sources=response.get("sources", []),
            sales_state=sales_state_payload,
            suggested_questions=suggested_questions,
        )


    except HTTPException:
        # Re-raise HTTPExceptions (such as 403, 404 from conversation ownership checks)
        raise

    except ValueError as e:
        logger.warning("ask validation error user_id=%d error=%s", current_user.id, str(e))
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:
        logger.error(
            "ask unexpected error user_id=%d error_type=%s message=%s",
            current_user.id,
            type(e).__name__,
            str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Response generation failed: {str(e)}",
        )