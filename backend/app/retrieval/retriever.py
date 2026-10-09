import os
from typing import Optional

from dotenv import load_dotenv
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.database.qdrant import client
from app.retrieval.embedder import embedder
from app.retrieval.schemas import (
    RetrievedChunk,
    RetrievalResponse,
)


load_dotenv()


COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "product_chunks")

TOP_K = int(
    os.getenv("RETRIEVAL_TOP_K", "5")
)

SCORE_THRESHOLD = float(
    os.getenv(
        "RETRIEVAL_SCORE_THRESHOLD",
        "0.0"
    )
)

_vector_name_cache: dict[str, Optional[str]] = {}


def _resolve_vector_name(collection_name: str) -> Optional[str]:
    """
    Check if the Qdrant collection uses named vectors (e.g. 'dense')
    and return the vector name to use for querying.
    """
    if collection_name in _vector_name_cache:
        return _vector_name_cache[collection_name]
    try:
        coll = client.get_collection(collection_name)
        vectors_config = coll.config.params.vectors
        if isinstance(vectors_config, dict):
            vname = "dense" if "dense" in vectors_config else next(iter(vectors_config.keys()), None)
            _vector_name_cache[collection_name] = vname
            return vname
        _vector_name_cache[collection_name] = None
        return None
    except Exception:
        return None


def build_filter(
    sku: Optional[str] = None,
    category: Optional[str] = None,
    manufacturer: Optional[str] = None,
    document_id: Optional[int] = None,
):
    conditions = []

    if sku is not None:
        conditions.append(
            FieldCondition(
                key="sku",
                match=MatchValue(
                    value=sku
                ),
            )
        )

    if category is not None:
        conditions.append(
            FieldCondition(
                key="category",
                match=MatchValue(
                    value=category
                ),
            )
        )

    if manufacturer is not None:
        conditions.append(
            FieldCondition(
                key="manufacturer",
                match=MatchValue(
                    value=manufacturer
                ),
            )
        )

    if document_id is not None:
        conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchValue(
                    value=document_id
                ),
            )
        )

    if not conditions:
        return None

    return Filter(
        must=conditions
    )


def retrieve(
    query: str,
    top_k: int = TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    sku: Optional[str] = None,
    category: Optional[str] = None,
    manufacturer: Optional[str] = None,
    document_id: Optional[int] = None,
) -> RetrievalResponse:

    # -----------------------------
    # Validate query
    # -----------------------------

    if not query or not query.strip():
        raise ValueError(
            "Query cannot be empty."
        )

    # -----------------------------
    # Validate top_k
    # -----------------------------

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than 0."
        )

    if top_k > 100:
        raise ValueError(
            "top_k cannot be greater than 100."
        )

    # -----------------------------
    # Validate score threshold
    # -----------------------------

    if score_threshold < -1.0:
        raise ValueError(
            "score_threshold cannot be below -1.0."
        )

    if score_threshold > 1.0:
        raise ValueError(
            "score_threshold cannot be above 1.0."
        )

    # -----------------------------
    # Query embedding
    # -----------------------------

    query_vector = embedder.embed_query(
        query
    )

    # -----------------------------
    # Metadata filter
    # -----------------------------

    query_filter = build_filter(
        sku=sku,
        category=category,
        manufacturer=manufacturer,
        document_id=document_id,
    )

    # -----------------------------
    # Qdrant search
    # -----------------------------

    query_kwargs = {
        "collection_name": COLLECTION_NAME,
        "query": query_vector,
        "query_filter": query_filter,
        "limit": top_k,
        "score_threshold": score_threshold,
        "with_payload": True,
    }

    vector_name = _resolve_vector_name(COLLECTION_NAME)
    if vector_name:
        query_kwargs["using"] = vector_name

    results = client.query_points(**query_kwargs).points

    # -----------------------------
    # Format results
    # -----------------------------

    retrieved_chunks = []

    for result in results:

        payload = result.payload or {}

        retrieved_chunks.append(
            RetrievedChunk(
                chunk_id=payload.get(
                    "chunk_id"
                ),
                document_id=payload.get(
                    "document_id"
                ),
                text=payload.get(
                    "text",
                    ""
                ),
                score=float(
                    result.score
                ),
                metadata={
                    "sku": payload.get("sku"),
                    "category": payload.get(
                        "category"
                    ),
                    "manufacturer": payload.get(
                        "manufacturer"
                    ),
                    "filename": payload.get(
                        "filename"
                    ),
                    "page_number": payload.get(
                        "page_number"
                    ),
                    "sheet_name": payload.get(
                        "sheet_name"
                    ),
                    "row_number": payload.get(
                        "row_number"
                    ),
                },
            )
        )

    return RetrievalResponse(
        query=query,
        results=retrieved_chunks,
        total_results=len(
            retrieved_chunks
        ),
    )