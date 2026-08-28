from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.models import User
from app.database.session import SessionLocal
from app.logging.query_logger import log_query

from app.retrieval.api_schemas import SearchRequest
from app.retrieval.retriever import retrieve
from app.generation.generator import generate_response
from app.generation.api_schemas import AskResponse


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

        # Step 1: Retrieve relevant chunks
        retrieval_response = retrieve(
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            sku=request.sku,
            category=request.category,
            manufacturer=request.manufacturer,
            document_id=request.document_id,
        )

        # Step 2: Generate final answer
        response = generate_response(
            query=request.query,
            retrieval_response=retrieval_response,
        )

        # Step 3: Log the user's query
        log_query(
            db=db,
            user_id=current_user.id,
            query=request.query,
        )

        return response

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Response generation failed: {str(e)}",
        )