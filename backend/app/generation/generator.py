import re
import os
from app.retrieval.schemas import RetrievalResponse
from app.generation.context_builder import build_context
from app.generation.prompt_builder import build_messages
from app.generation.llm import generate_llm_response

from dotenv import load_dotenv

load_dotenv()

MINIMUM_RELEVANCE_SCORE=float(
    os.getenv(
        "RETRIEVAL_MINIMUM_SCORE",
        "0.5"
    )
)

def filter_relevant_chunks(
    retrieval_response: RetrievalResponse,
    minimum_score: float = 0.5,
):
    relevant_chunks = []

    for chunk in retrieval_response.results:

        if chunk.score >= minimum_score:
            relevant_chunks.append(chunk)

    return relevant_chunks


def generate_response(
    query: str,
    retrieval_response: RetrievalResponse,
) -> dict:

    # No retrieval results
    if retrieval_response.total_results == 0:

        return {
            "query": query,
            "answer": (
                "No relevant information was found "
                "in the product catalog."
            ),
            "sources": [],
        }

    # Filter low-confidence chunks
    relevant_chunks = filter_relevant_chunks(
        retrieval_response,
        minimum_score=MINIMUM_RELEVANCE_SCORE,
    )

    # All results were below threshold
    if not relevant_chunks:

        return {
            "query": query,
            "answer": (
                "No sufficiently relevant information "
                "was found in the product catalog."
            ),
            "sources": [],
        }

    # Create filtered response
    filtered_response = RetrievalResponse(
        query=retrieval_response.query,
        results=relevant_chunks,
        total_results=len(relevant_chunks),
    )

    # Build context
    context = build_context(
        filtered_response
    )

    # Build prompt
    messages = build_messages(
        query=query,
        context=context,
    )

    # Generate answer
    answer = generate_llm_response(
        messages=messages
    )

    # Remove Qwen reasoning output
    answer = re.sub(
        r"<think>.*?</think>",
        "",
        answer,
        flags=re.DOTALL,
    ).strip()

    # Extract unique sources
    sources = []
    seen_sources = set()

    for chunk in filtered_response.results:

        sku = chunk.metadata.get("sku")
        document_id = chunk.document_id

        source_key = (
            document_id,
            sku,
        )

        if source_key in seen_sources:
            continue

        seen_sources.add(source_key)

        sources.append(
            {
                "chunk_id": chunk.chunk_id,
                "document_id": document_id,
                "sku": sku,
                "filename": chunk.metadata.get(
                    "filename"
                ),
            }
        )

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
    }