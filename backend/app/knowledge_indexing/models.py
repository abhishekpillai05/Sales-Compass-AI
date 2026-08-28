"""
Knowledge Indexing Service — input/output data contracts.

This module defines the shared data structures that form the interface
between the Document Ingestion Service (Phase 3) and the Knowledge
Indexing Service (Phase 4).

Phase 3 produces ChunkInput objects; Phase 4 consumes them.

Changes vs origin/phase-4:
- ChunkMetadata gains document_id, sheet_name, row_number so that the
  bridge adapter can preserve all Phase 3 metadata without data loss.
- text is NOT stored inside ChunkMetadata; it lives in ChunkInput.text.
  The Qdrant payload builder in indexer.py injects text from ChunkInput.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ChunkMetadata:
    """
    Metadata attached to a document chunk.

    All fields are optional because not every document type carries
    every field. Missing values default to None.

    Note: 'text' is intentionally absent here — it lives in
    ChunkInput.text to avoid duplication.
    """

    sku: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    filename: Optional[str] = None
    page_number: Optional[int] = None

    # Extended fields added for Phase 3 -> Phase 4 bridge compatibility.
    document_id: Optional[Any] = None   # PostgreSQL Document PK (int or str)
    sheet_name: Optional[str] = None    # Excel sheet name, if applicable
    row_number: Optional[int] = None    # CSV/Excel row number, if applicable

    def to_dict(self) -> dict:
        """
        Return a plain dict suitable for Qdrant payload.

        Note: 'text' is NOT included here because it is injected by the
        indexer from ChunkInput.text so it appears exactly once in the
        Qdrant payload without duplication.
        """
        return {
            "sku": self.sku,
            "category": self.category,
            "manufacturer": self.manufacturer,
            "filename": self.filename,
            "page_number": self.page_number,
            "document_id": self.document_id,
            "sheet_name": self.sheet_name,
            "row_number": self.row_number,
        }


@dataclass
class ChunkInput:
    """
    The canonical input contract for the Knowledge Indexing Service.

    Produced by the Document Ingestion Service (Phase 3) via the bridge
    adapter and consumed by this service (Phase 4).

    chunk_id must be globally unique and stable across re-indexing runs.
    text must be a non-empty, clean string (whitespace-stripped).
    metadata carries SKU/category/manufacturer/filename/page + extended fields.
    """

    chunk_id: str
    text: str
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    @classmethod
    def from_dict(cls, data: dict) -> "ChunkInput":
        """
        Construct a ChunkInput from a plain dictionary.

        Accepts the documented JSON contract:
        {
            "chunk_id": "...",
            "text": "...",
            "metadata": {
                "sku": "...",
                "category": "...",
                "manufacturer": "...",
                "filename": "...",
                "page_number": 1,
                "document_id": 42,
                "sheet_name": "Sheet1",
                "row_number": 3
            }
        }
        """
        raw_meta = data.get("metadata", {})
        metadata = ChunkMetadata(
            sku=raw_meta.get("sku"),
            category=raw_meta.get("category"),
            manufacturer=raw_meta.get("manufacturer"),
            filename=raw_meta.get("filename"),
            page_number=raw_meta.get("page_number"),
            document_id=raw_meta.get("document_id"),
            sheet_name=raw_meta.get("sheet_name"),
            row_number=raw_meta.get("row_number"),
        )
        return cls(
            chunk_id=data["chunk_id"],
            text=data["text"],
            metadata=metadata,
        )


@dataclass
class IndexingResult:
    """
    The output contract returned by the indexer after processing a chunk.

    chunk_id:        The same chunk_id that was submitted.
    success:         True if both Qdrant and PostgreSQL writes succeeded.
    qdrant_point_id: The UUID string used as the Qdrant point identifier.
    error:           Human-readable error message if success=False, else None.
    """

    chunk_id: str
    success: bool
    qdrant_point_id: Optional[str] = None
    error: Optional[str] = None
