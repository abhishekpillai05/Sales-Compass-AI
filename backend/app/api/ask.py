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
from app.generation.api_schemas import AskResponse

from app.conversation.service import (
    create_conversation,
    get_conversation,
    get_recent_messages,
    add_message,
)
from app.conversation.contextualizer import contextualize_query


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

        # Step 4: Generate final answer with conversation history and retrieved context
        history_for_llm = [
            {"role": m.role, "content": m.content}
            for m in history_messages
        ]

        response = generate_response(
            query=request.query,
            retrieval_response=retrieval_response,
            conversation_history=history_for_llm,
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

        # Step 6: Log the user's query (Phase 7 query logging — preserved)
        log_query(
            db=db,
            user_id=current_user.id,
            query=request.query,
        )

        logger.info(
            "ask completed user_id=%d conversation_id=%d chunks_retrieved=%d",
            current_user.id,
            conversation_id,
            retrieval_response.total_results,
        )

        return AskResponse(
            query=request.query,
            answer=response["answer"],
            conversation_id=conversation_id,
            sources=response.get("sources", []),
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