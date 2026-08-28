from app.retrieval.schemas import RetrievalResponse


def build_context(
    retrieval_response: RetrievalResponse,
) -> str:
    """
    Convert retrieved chunks into structured
    context for the LLM.
    """

    if retrieval_response.total_results == 0:
        return ""

    context_parts = []

    for index, chunk in enumerate(
        retrieval_response.results,
        start=1,
    ):

        metadata = chunk.metadata

        context = f"""
[Source {index}]

Chunk ID: {chunk.chunk_id}
Document ID: {chunk.document_id}

SKU: {metadata.get("sku")}
Category: {metadata.get("category")}
Manufacturer: {metadata.get("manufacturer")}

Content:
{chunk.text}
"""

        context_parts.append(
            context.strip()
        )

    return "\n\n".join(context_parts)