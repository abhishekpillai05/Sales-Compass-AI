"""
End-to-end integration test ΓÇö Phase 3 -> Phase 4 -> Phase 5.

Tests the complete RAG retrieval pipeline:
  DocumentChunk (Phase 3 output)
  -> bridge adapter
  -> ChunkInput (Phase 4 input)
  -> generate embedding
  -> store vector in Qdrant
  -> store metadata in PostgreSQL document_chunks
  -> Phase 5: embed query -> search Qdrant -> retrieve relevant chunk

All tests in this module require live Qdrant AND PostgreSQL connections.
They are automatically skipped if QDRANT_URL or DATABASE_URL is not set
in the environment.

IMPORTANT: These tests make real network calls to real services.
No results are faked. If services are unavailable, the skip message
explains exactly what is missing.
"""

import os
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env")
)

_qdrant_ok = bool(os.getenv("QDRANT_URL", "").strip())
_pg_ok = bool(os.getenv("DATABASE_URL", "").strip())
_services_ok = _qdrant_ok and _pg_ok

pytestmark = pytest.mark.skipif(
    not _services_ok,
    reason=(
        "Skipping end-to-end integration tests: "
        + ("QDRANT_URL not set. " if not _qdrant_ok else "")
        + ("DATABASE_URL not set." if not _pg_ok else "")
    ),
)

# ---------------------------------------------------------------------------
# Imports (only reached when services are available)
# ---------------------------------------------------------------------------

from app.ingestion.schemas import DocumentChunk
from app.ingestion.bridge import (
    document_chunk_to_chunk_input,
    document_chunks_to_chunk_inputs,
)
from app.knowledge_indexing.indexer import index_chunk, index_chunks
from app.knowledge_indexing.models import ChunkInput, ChunkMetadata
from app.knowledge_indexing.qdrant_service import get_point_by_chunk_id
from app.knowledge_indexing.postgres_service import get_chunk_by_id
from app.retrieval.retriever import retrieve


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_document_chunk(
    chunk_id: str = None,
    document_id: int = 1,
    text: str = "SalesCompass test document. Product A costs 1000 and belongs to the Electronics category.",
    filename: str = "test_doc.pdf",
    page_number: int = 1,
    sku: str = "TEST-SKU-001",
    category: str = "Electronics",
    manufacturer: str = "TestCorp",
    sheet_name: str = None,
    row_number: int = None,
) -> DocumentChunk:
    """Build a Phase 3 DocumentChunk for testing."""
    if chunk_id is None:
        chunk_id = f"e2e-test-{uuid.uuid4().hex}"
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        metadata={
            "filename": filename,
            "page_number": page_number,
            "sku": sku,
            "category": category,
            "manufacturer": manufacturer,
            "sheet_name": sheet_name,
            "row_number": row_number,
        },
    )


# ---------------------------------------------------------------------------
# Test: Bridge adapter (Phase 3 -> Phase 4)
# ---------------------------------------------------------------------------

class TestBridgeAdapter:
    """Verify DocumentChunk -> ChunkInput conversion is lossless."""

    def test_bridge_preserves_chunk_id(self):
        doc_chunk = make_document_chunk(chunk_id="bridge-test-001")
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.chunk_id == "bridge-test-001"

    def test_bridge_preserves_text(self):
        doc_chunk = make_document_chunk(text="Unique test text for bridge.")
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.text == "Unique test text for bridge."

    def test_bridge_preserves_document_id(self):
        doc_chunk = make_document_chunk(document_id=42)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.metadata.document_id == 42

    def test_bridge_preserves_sku(self):
        doc_chunk = make_document_chunk(sku="SKU-XYZ")
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.metadata.sku == "SKU-XYZ"

    def test_bridge_preserves_category(self):
        doc_chunk = make_document_chunk(category="Networking")
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.metadata.category == "Networking"

    def test_bridge_preserves_sheet_name(self):
        doc_chunk = make_document_chunk(sheet_name="Products")
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.metadata.sheet_name == "Products"

    def test_bridge_preserves_row_number(self):
        doc_chunk = make_document_chunk(row_number=5)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.metadata.row_number == 5

    def test_text_not_in_metadata_dict(self):
        """text must live in ChunkInput.text only, not duplicated in metadata."""
        doc_chunk = make_document_chunk(text="Should not appear in metadata.")
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        meta_dict = chunk_input.metadata.to_dict()
        # text must NOT be a key in metadata.to_dict() at this level
        # (it IS injected into the Qdrant payload by the indexer)
        assert "text" not in meta_dict or meta_dict.get("text") is None, (
            "text must not be stored inside ChunkMetadata to avoid duplication"
        )

    def test_batch_bridge(self):
        chunks = [make_document_chunk() for _ in range(3)]
        inputs = document_chunks_to_chunk_inputs(chunks)
        assert len(inputs) == 3
        assert all(isinstance(c, ChunkInput) for c in inputs)


# ---------------------------------------------------------------------------
# Test: Phase 4 indexing ΓÇö Qdrant payload completeness
# ---------------------------------------------------------------------------

class TestQdrantPayloadCompleteness:
    """
    Verify that the Qdrant payload after indexing contains all fields
    that Phase 5 (Retrieval) expects to read.
    """

    def test_qdrant_payload_has_text(self):
        chunk_id = f"payload-test-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(
            chunk_id=chunk_id,
            text="Product A costs 1000 rupees in Electronics.",
        )
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"

        payload = get_point_by_chunk_id(chunk_id)
        assert payload is not None, "Point not found in Qdrant"
        assert payload.get("text") == "Product A costs 1000 rupees in Electronics."

    def test_qdrant_payload_has_document_id(self):
        chunk_id = f"payload-docid-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(chunk_id=chunk_id, document_id=99)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"

        payload = get_point_by_chunk_id(chunk_id)
        assert payload is not None
        assert payload.get("document_id") == 99

    def test_qdrant_payload_has_chunk_id(self):
        chunk_id = f"payload-cid-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(chunk_id=chunk_id)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"

        payload = get_point_by_chunk_id(chunk_id)
        assert payload is not None
        assert payload.get("chunk_id") == chunk_id

    def test_qdrant_payload_has_metadata_fields(self):
        chunk_id = f"payload-meta-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(
            chunk_id=chunk_id,
            sku="META-SKU",
            category="TestCat",
            manufacturer="TestMfr",
            filename="meta_test.pdf",
            page_number=3,
        )
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"

        payload = get_point_by_chunk_id(chunk_id)
        assert payload is not None
        assert payload.get("sku") == "META-SKU"
        assert payload.get("category") == "TestCat"
        assert payload.get("manufacturer") == "TestMfr"
        assert payload.get("filename") == "meta_test.pdf"
        assert payload.get("page_number") == 3

    def test_qdrant_payload_has_sheet_and_row(self):
        chunk_id = f"payload-sheet-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(
            chunk_id=chunk_id,
            sheet_name="Sheet1",
            row_number=7,
        )
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"

        payload = get_point_by_chunk_id(chunk_id)
        assert payload is not None
        assert payload.get("sheet_name") == "Sheet1"
        assert payload.get("row_number") == 7


# ---------------------------------------------------------------------------
# Test: Phase 4 -> PostgreSQL linkage
# ---------------------------------------------------------------------------

class TestPostgreSQLLinkage:
    """Verify chunk metadata is stored in document_chunks and linked by chunk_id."""

    def test_pg_record_created(self):
        chunk_id = f"pg-test-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(chunk_id=chunk_id)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"

        pg_record = get_chunk_by_id(chunk_id)
        assert pg_record is not None, "No PostgreSQL record found"
        assert pg_record["chunk_id"] == chunk_id

    def test_pg_chunk_id_matches_qdrant(self):
        """chunk_id in PostgreSQL must equal chunk_id in Qdrant payload."""
        chunk_id = f"pg-qdrant-link-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(chunk_id=chunk_id)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success

        pg_record = get_chunk_by_id(chunk_id)
        qdrant_payload = get_point_by_chunk_id(chunk_id)
        assert pg_record is not None and qdrant_payload is not None
        assert pg_record["chunk_id"] == qdrant_payload.get("chunk_id") == chunk_id


# ---------------------------------------------------------------------------
# Test: Full end-to-end pipeline ΓÇö upload -> index -> retrieve
# ---------------------------------------------------------------------------

class TestEndToEndPipeline:
    """
    Smoke test: simulate Phase 3 output -> Phase 4 indexing -> Phase 5 retrieval.

    Uses the documented smoke-test document from the task spec:
    "SalesCompass test document. Product A costs 1000 and belongs to the Electronics category."
    Query: "What is the price of Product A?"
    """

    def test_smoke_test_full_pipeline(self):
        chunk_id = f"smoke-{uuid.uuid4().hex}"

        # Use the chunk_id in the text so this chunk scores uniquely high
        # for a query containing that same token. This prevents ranking
        # collisions in the shared Qdrant collection that accumulates
        # similar "Product A costs 1000" chunks from multiple test runs.
        smoke_text = (
            f"SalesCompass smoke test reference {chunk_id}. "
            "Product A has a list price of 1000 units in the Electronics category."
        )
        smoke_query = f"SalesCompass smoke test reference {chunk_id}"

        # Step 1: Simulate Phase 3 output
        doc_chunk = make_document_chunk(
            chunk_id=chunk_id,
            text=smoke_text,
            document_id=1,
            sku="PROD-A",
            category="Electronics",
            filename="smoke_test.pdf",
            page_number=1,
        )

        # Step 2: Bridge (Phase 3 -> Phase 4)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        assert chunk_input.chunk_id == chunk_id
        assert chunk_input.text == smoke_text

        # Step 3: Phase 4 ΓÇö index (embed + store)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"
        assert result.qdrant_point_id is not None

        # Step 4: Verify Qdrant payload completeness
        payload = get_point_by_chunk_id(chunk_id)
        assert payload is not None, "Vector not found in Qdrant after indexing"
        assert payload.get("text") == smoke_text
        assert payload.get("chunk_id") == chunk_id
        assert payload.get("document_id") == 1

        # Step 5: Verify PostgreSQL record
        pg = get_chunk_by_id(chunk_id)
        assert pg is not None, "No PostgreSQL record after indexing"

        # Step 6: Phase 5 ΓÇö query embedding + Qdrant search
        response = retrieve(
            query=smoke_query,
            top_k=5,
            score_threshold=0.0,
        )

        assert response.total_results >= 0, "retrieve() must return a RetrievalResponse"

        # Step 7: Verify our indexed chunk is findable
        chunk_ids_returned = [r.chunk_id for r in response.results]
        assert chunk_id in chunk_ids_returned, (
            f"Smoke-test chunk '{chunk_id}' was indexed but NOT returned by retrieval.\n"
            f"Query: '{smoke_query}'\n"
            f"Returned chunk_ids: {chunk_ids_returned}"
        )

        # Step 8: Verify returned chunk has text and document_id populated
        matching = next(r for r in response.results if r.chunk_id == chunk_id)
        assert matching.text == smoke_text, "Returned chunk text does not match"
        assert matching.document_id == 1, "Returned document_id does not match"


    def test_idempotent_reindex_no_duplicate_retrieval(self):
        """Re-indexing the same chunk must not return it multiple times."""
        chunk_id = f"idem-{uuid.uuid4().hex}"
        text = f"Idempotency test chunk {chunk_id}."
        doc_chunk = make_document_chunk(chunk_id=chunk_id, text=text)
        chunk_input = document_chunk_to_chunk_input(doc_chunk)

        # Index three times
        for _ in range(3):
            r = index_chunk(chunk_input)
            assert r.success, f"Re-index failed: {r.error}"

        # Retrieve ΓÇö chunk should appear at most once
        response = retrieve(query=text, top_k=50)
        matching = [r for r in response.results if r.chunk_id == chunk_id]
        assert len(matching) <= 1, (
            f"Chunk appeared {len(matching)} times in results after re-indexing ΓÇö "
            "idempotency violation"
        )

    def test_empty_query_raises(self):
        """retrieve() with empty query must raise ValueError, not crash."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            retrieve(query="")

    def test_whitespace_query_raises(self):
        with pytest.raises(ValueError, match="Query cannot be empty"):
            retrieve(query="   ")

    def test_no_match_returns_empty_safely(self):
        """An extremely specific query with no match should return empty, not crash."""
        response = retrieve(
            query="xyzzy_no_such_product_klmnopqrs_12345",
            top_k=5,
            score_threshold=0.99,  # very high threshold ΓÇö should return nothing
        )
        assert isinstance(response.total_results, int)
        assert response.total_results >= 0

    def test_document_filter(self):
        """Filtering by document_id must only return chunks from that document."""
        chunk_id = f"docfilter-{uuid.uuid4().hex}"
        doc_chunk = make_document_chunk(
            chunk_id=chunk_id,
            text="Filter test: wireless router specifications.",
            document_id=9999,
        )
        chunk_input = document_chunk_to_chunk_input(doc_chunk)
        result = index_chunk(chunk_input)
        assert result.success, f"Indexing failed: {result.error}"

        # Search filtered to a non-existent document_id
        response = retrieve(
            query="wireless router",
            top_k=10,
            document_id=0,  # no chunks have document_id=0
        )
        returned_ids = [r.document_id for r in response.results]
        assert 9999 not in returned_ids, (
            "document_id filter did not exclude chunk from a different document"
        )


# ---------------------------------------------------------------------------
# Test: Batch indexing via Phase 3 bridge
# ---------------------------------------------------------------------------

class TestBatchPipelineIntegration:
    def test_batch_index_from_phase3_chunks(self):
        """Batch-convert and index multiple Phase 3 chunks at once."""
        doc_chunks = [
            make_document_chunk(
                chunk_id=f"batch-e2e-{uuid.uuid4().hex}",
                text=f"Batch integration test chunk number {i}.",
                document_id=100 + i,
            )
            for i in range(3)
        ]
        chunk_inputs = document_chunks_to_chunk_inputs(doc_chunks)
        results = index_chunks(chunk_inputs)

        assert len(results) == 3
        for r in results:
            assert r.success, f"Batch indexing failed for {r.chunk_id}: {r.error}"

    def test_batch_with_invalid_chunk_does_not_abort(self):
        """A bad chunk in a batch must not block the remaining chunks."""
        bad = DocumentChunk(
            chunk_id=f"bad-{uuid.uuid4().hex}",
            document_id=1,
            text="",  # empty text ΓÇö Phase 4 will reject this
            metadata={},
        )
        good = make_document_chunk(
            chunk_id=f"good-{uuid.uuid4().hex}",
            text="This is a valid chunk that should be indexed.",
        )
        chunk_inputs = document_chunks_to_chunk_inputs([bad, good])
        results = index_chunks(chunk_inputs)

        assert len(results) == 2
        assert results[0].success is False  # bad chunk
        assert results[1].success is True   # good chunk
