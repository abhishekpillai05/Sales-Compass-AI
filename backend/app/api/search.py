from fastapi import APIRouter, HTTPException

from app.retrieval.api_schemas import SearchRequest
from app.retrieval.retriever import retrieve
from app.logging.config import get_logger


logger = get_logger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["Retrieval"],
)


@router.post("")
def search(request: SearchRequest):

    try:

        response = retrieve(
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            sku=request.sku,
            category=request.category,
            manufacturer=request.manufacturer,
            document_id=request.document_id,
        )

        logger.info(
            "search completed query_length=%d results=%d",
            len(request.query),
            response.total_results,
        )

        return response

    except ValueError as e:

        logger.warning("search validation error error=%s", str(e))

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:

        logger.error(
            "search unexpected error error_type=%s message=%s",
            type(e).__name__,
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=f"Retrieval failed: {str(e)}",
        )