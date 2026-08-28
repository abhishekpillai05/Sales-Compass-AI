"""
Bridge adapter: Phase 3 DocumentChunk -> Phase 4 ChunkInput.

This module is the single integration point between the Document Ingestion
Service (Phase 3) and the Knowledge Indexing Service (Phase 4).

It converts the plain-dict metadata produced by Phase 3 into the typed
ChunkMetadata dataclass expected by Phase 4, preserving all fields
(including document_id, sheet_name, and row_number) without data loss.

Design decisions:
- text lives in ChunkInput.text only; it is NOT duplicated inside
  ChunkMetadata, to avoid redundancy.
- document_id, sheet_name, row_number are carried through ChunkMetadata
  so they end up in the Qdrant payload and can be used by Phase 5.
- No validation is performed here beyond what Phase 4 already enforces;
  this adapter is intentionally thin.
"""

from typing import List

from app.ingestion.schemas import DocumentChunk
from app.knowledge_indexing.models import ChunkInput, ChunkMetadata


def document_chunk_to_chunk_input(chunk: DocumentChunk) -> ChunkInput:
    """
    Convert a single Phase 3 DocumentChunk to a Phase 4 ChunkInput.

    Parameters
    ----------
    chunk : DocumentChunk
        Output of the Phase 3 ingestion pipeline.

    Returns
    -------
    ChunkInput
        Ready to pass directly to index_chunk() or index_chunks().
    """
    meta = chunk.metadata if isinstance(chunk.metadata, dict) else {}

    return ChunkInput(
        chunk_id=chunk.chunk_id,
        text=chunk.text,
        metadata=ChunkMetadata(
            sku=meta.get("sku"),
            category=meta.get("category"),
            manufacturer=meta.get("manufacturer"),
            filename=meta.get("filename"),
            page_number=meta.get("page_number"),
            # Extended fields — absent from original ChunkMetadata in phase-4
            document_id=chunk.document_id,
            sheet_name=meta.get("sheet_name"),
            row_number=meta.get("row_number"),
        ),
    )


def document_chunks_to_chunk_inputs(
    chunks: List[DocumentChunk],
) -> List[ChunkInput]:
    """
    Batch-convert a list of Phase 3 DocumentChunks to Phase 4 ChunkInputs.

    Parameters
    ----------
    chunks : List[DocumentChunk]
        List of chunks produced by process_document().

    Returns
    -------
    List[ChunkInput]
        Same length and order as the input list.
    """
    return [document_chunk_to_chunk_input(c) for c in chunks]
