"""
tests/test_document_hashing.py

Comprehensive tests for Document Content Hashing and Duplicate Detection.

Test coverage:
  1. SAME_CONTENT_DIFFERENT_FILENAMES  — same bytes → same hash
  2. DIFFERENT_CONTENT                 — different bytes → different hashes
  3. DETERMINISM                       — repeated hashes on same file
  4. EMPTY_FILE                        — valid, deterministic, correct format
  5. LARGE_FILE                        — chunked reading verified
  6. HASH_FORMAT                       — len==64, all hex chars
  7. MISSING_FILE                      — FileNotFoundError propagated
  8. DUPLICATE_UPLOAD_API              — second upload returns 409 Conflict,
                                         no re-indexing
  9. SAME_CONTENT_DIFFERENT_FILENAME_API
                                       — catalog.pdf then catalog_final.pdf
                                         with identical bytes → 409
 10. CONCURRENT_DUPLICATE_UPLOAD       — UNIQUE constraint blocks both
                                         concurrent uploads creating two rows

These tests are split into two groups:
  - Pure unit tests (no DB, no HTTP) — always run.
  - Integration tests (require DATABASE_URL in .env) — skipped when env var absent.
"""

import hashlib
import io
import os
import threading
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

# Load .env early so DATABASE_URL is available when deciding to skip.
load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env")
)

_pg_ok = bool(os.getenv("DATABASE_URL", "").strip())

# ---------------------------------------------------------------------------
# Shared helper: SHA-256 of known bytes (reference value)
# ---------------------------------------------------------------------------

_KNOWN_CONTENT = b"SalesCompass AI hashing test content \xde\xad\xbe\xef"
_KNOWN_HASH = hashlib.sha256(_KNOWN_CONTENT).hexdigest()
_EMPTY_HASH = hashlib.sha256(b"").hexdigest()  # canonical empty-file SHA-256


# ===========================================================================
# GROUP 1 — Pure unit tests for calculate_file_hash()
# ===========================================================================

class TestCalculateFileHashUnit:
    """Pure filesystem tests — no database or HTTP calls."""

    # ── 1. Same content / different filenames ────────────────────────────────

    def test_same_content_different_filenames_produce_same_hash(self, tmp_path):
        """Two files with identical bytes must produce identical SHA-256 digests."""
        content = b"identical content for both files \x00\x01\x02\x03"
        file_a = tmp_path / "file_a.pdf"
        file_b = tmp_path / "file_b.pdf"
        file_a.write_bytes(content)
        file_b.write_bytes(content)

        from app.ingestion.hasher import calculate_file_hash

        hash_a = calculate_file_hash(file_a)
        hash_b = calculate_file_hash(file_b)

        assert hash_a == hash_b, (
            "Files with identical binary content must produce the same hash "
            f"regardless of filename. Got: {hash_a!r} vs {hash_b!r}"
        )

    def test_hash_is_independent_of_filename(self, tmp_path):
        """Renaming a file must not change its hash."""
        from app.ingestion.hasher import calculate_file_hash

        content = b"hash must not depend on filename"
        f1 = tmp_path / "catalog.pdf"
        f2 = tmp_path / "catalog_final_v3_APPROVED.pdf"
        f1.write_bytes(content)
        f2.write_bytes(content)

        assert calculate_file_hash(f1) == calculate_file_hash(f2)

    # ── 2. Different content ──────────────────────────────────────────────────

    def test_different_content_produces_different_hashes(self, tmp_path):
        """Files with different bytes must produce different hashes."""
        from app.ingestion.hasher import calculate_file_hash

        file_a = tmp_path / "file_a.pdf"
        file_b = tmp_path / "file_b.pdf"
        file_a.write_bytes(b"content alpha \x01")
        file_b.write_bytes(b"content beta  \x02")

        assert calculate_file_hash(file_a) != calculate_file_hash(file_b)

    # ── 3. Determinism ────────────────────────────────────────────────────────

    def test_hash_is_deterministic_across_repeated_calls(self, tmp_path):
        """Hashing the same file multiple times must always return the same value."""
        from app.ingestion.hasher import calculate_file_hash

        f = tmp_path / "determinism.pdf"
        f.write_bytes(_KNOWN_CONTENT)

        hashes = [calculate_file_hash(f) for _ in range(5)]
        assert len(set(hashes)) == 1, f"Non-deterministic! Got: {hashes}"
        assert hashes[0] == _KNOWN_HASH

    # ── 4. Empty file ─────────────────────────────────────────────────────────

    def test_empty_file_hashing_succeeds(self, tmp_path):
        """Zero-byte files are valid; hashing must not raise."""
        from app.ingestion.hasher import calculate_file_hash

        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")

        result = calculate_file_hash(empty)
        assert result == _EMPTY_HASH

    def test_empty_file_hash_is_deterministic(self, tmp_path):
        """Empty file hash must be the same on repeated calls."""
        from app.ingestion.hasher import calculate_file_hash

        empty = tmp_path / "empty2.pdf"
        empty.write_bytes(b"")

        h1 = calculate_file_hash(empty)
        h2 = calculate_file_hash(empty)
        assert h1 == h2

    def test_empty_file_hash_is_valid_hex(self, tmp_path):
        """Empty file hash must be a valid 64-char hex string."""
        from app.ingestion.hasher import calculate_file_hash

        empty = tmp_path / "empty3.pdf"
        empty.write_bytes(b"")

        result = calculate_file_hash(empty)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result), (
            f"Non-hex character in hash: {result!r}"
        )

    # ── 5. Large file ─────────────────────────────────────────────────────────

    def test_large_file_hashing_succeeds(self, tmp_path):
        """Hashing a 4 MB file must succeed without error."""
        from app.ingestion.hasher import calculate_file_hash

        large = tmp_path / "large_catalog.pdf"
        # 4 MB of pseudo-random bytes
        large.write_bytes(os.urandom(4 * 1024 * 1024))

        result = calculate_file_hash(large)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_large_file_hash_uses_chunked_reading(self, tmp_path, monkeypatch):
        """
        Verify that the implementation reads the file in chunks rather than
        loading all bytes at once with read() (no size argument).

        Strategy: monkeypatch the file object so that read() *without* a size
        argument raises AssertionError, while read(n) succeeds normally.
        This catches any refactoring that accidentally removes the chunk size.
        """
        from app.ingestion import hasher

        real_open = builtins_open = open

        def patched_open(path, mode="r", **kwargs):
            f = real_open(path, mode, **kwargs)
            if "b" not in mode:
                return f

            original_read = f.read

            def guarded_read(size=-1):
                if size == -1 or size is None:
                    raise AssertionError(
                        "calculate_file_hash() called file.read() without a "
                        "chunk size — must use incremental reading."
                    )
                return original_read(size)

            f.read = guarded_read
            return f

        large = tmp_path / "large_chunked.pdf"
        large.write_bytes(os.urandom(2 * 1024 * 1024))

        import builtins
        monkeypatch.setattr(builtins, "open", patched_open)

        # Should NOT raise — proves chunked reading is used.
        result = hasher.calculate_file_hash(large)
        assert len(result) == 64

    # ── 6. Hash format ────────────────────────────────────────────────────────

    def test_hash_is_64_characters(self, tmp_path):
        from app.ingestion.hasher import calculate_file_hash

        f = tmp_path / "format_test.pdf"
        f.write_bytes(_KNOWN_CONTENT)
        assert len(calculate_file_hash(f)) == 64

    def test_hash_contains_only_hex_characters(self, tmp_path):
        from app.ingestion.hasher import calculate_file_hash

        f = tmp_path / "hex_test.pdf"
        f.write_bytes(_KNOWN_CONTENT)
        result = calculate_file_hash(f)
        assert all(c in "0123456789abcdef" for c in result), (
            f"Non-hex character found in: {result!r}"
        )

    def test_hash_matches_reference_value(self, tmp_path):
        """Verify against a known, independently computed SHA-256 digest."""
        from app.ingestion.hasher import calculate_file_hash

        f = tmp_path / "reference.pdf"
        f.write_bytes(_KNOWN_CONTENT)
        assert calculate_file_hash(f) == _KNOWN_HASH

    # ── 7. Missing file ───────────────────────────────────────────────────────

    def test_missing_file_raises_file_not_found_error(self, tmp_path):
        """calculate_file_hash() must propagate FileNotFoundError for absent files."""
        from app.ingestion.hasher import calculate_file_hash

        missing = tmp_path / "does_not_exist.pdf"
        with pytest.raises(FileNotFoundError):
            calculate_file_hash(missing)

    def test_missing_file_accepts_string_path(self, tmp_path):
        """String path variant must also raise FileNotFoundError."""
        from app.ingestion.hasher import calculate_file_hash

        missing_str = str(tmp_path / "also_missing.pdf")
        with pytest.raises(FileNotFoundError):
            calculate_file_hash(missing_str)

    # ── Additional: path types ────────────────────────────────────────────────

    def test_accepts_string_path(self, tmp_path):
        from app.ingestion.hasher import calculate_file_hash

        f = tmp_path / "string_path.pdf"
        f.write_bytes(b"string path test")
        # Should not raise even with a plain str
        result = calculate_file_hash(str(f))
        assert len(result) == 64

    def test_accepts_path_object(self, tmp_path):
        from app.ingestion.hasher import calculate_file_hash

        f = tmp_path / "path_obj.pdf"
        f.write_bytes(b"Path object test")
        result = calculate_file_hash(Path(f))
        assert len(result) == 64

    def test_binary_files_supported(self, tmp_path):
        """Binary (non-text) files must hash correctly."""
        from app.ingestion.hasher import calculate_file_hash

        f = tmp_path / "binary.xlsx"
        f.write_bytes(bytes(range(256)) * 100)  # arbitrary binary data
        result = calculate_file_hash(f)
        assert len(result) == 64


# ===========================================================================
# GROUP 2 — Integration tests: ingest_document() + duplicate detection
# ===========================================================================

@pytest.mark.skipif(
    not _pg_ok,
    reason="DATABASE_URL not set — skipping duplicate-detection integration tests.",
)
class TestDuplicateDetectionIntegration:
    """
    Tests that exercise the full ingest_document() service with a real (or
    mocked) database session.  These tests do NOT make real Qdrant calls;
    file processing is mocked to keep them fast and isolated.
    """

    def _make_minimal_pdf_bytes(self) -> bytes:
        """Return bytes that pass the PDF extension validator."""
        return b"%PDF-1.4 minimal test document " + os.urandom(64)

    def _make_db_session(self):
        from app.database.session import SessionLocal
        return SessionLocal()

    def test_first_upload_stores_hash(self, tmp_path):
        """
        First upload of a new file must create a Document record with a
        non-None, 64-char hex document_hash.
        """
        from app.ingestion.service import ingest_document
        from app.ingestion.exceptions import DuplicateDocumentError
        from app.database.models import Document

        db = self._make_db_session()
        content = self._make_minimal_pdf_bytes()
        unique_content = content + uuid.uuid4().bytes  # ensure uniqueness

        try:
            with patch("app.ingestion.service.process_document") as mock_proc:
                mock_proc.return_value = []
                result = ingest_document(
                    db=db,
                    filename=f"first_upload_{uuid.uuid4().hex}.pdf",
                    file_content=unique_content,
                )

            assert "document_hash" in result
            assert result["document_hash"] is not None
            assert len(result["document_hash"]) == 64
            assert all(c in "0123456789abcdef" for c in result["document_hash"])

            # Verify persisted in DB
            doc = db.query(Document).filter(
                Document.id == result["document_id"]
            ).first()
            assert doc is not None
            assert doc.document_hash == result["document_hash"]

        finally:
            # Cleanup
            doc = db.query(Document).filter(
                Document.id == result.get("document_id")
            ).first()
            if doc:
                db.delete(doc)
                db.commit()
            db.close()

    def test_duplicate_upload_raises_duplicate_document_error(self, tmp_path):
        """
        Uploading the same binary content twice must raise DuplicateDocumentError
        on the second call without creating a second DB record.
        """
        from app.ingestion.service import ingest_document
        from app.ingestion.exceptions import DuplicateDocumentError
        from app.database.models import Document

        db = self._make_db_session()
        content = self._make_minimal_pdf_bytes() + uuid.uuid4().bytes

        first_doc_id = None
        try:
            with patch("app.ingestion.service.process_document") as mock_proc:
                mock_proc.return_value = []

                # First upload — must succeed
                result1 = ingest_document(
                    db=db,
                    filename="catalog.pdf",
                    file_content=content,
                )
                first_doc_id = result1["document_id"]

                # Second upload with SAME content, DIFFERENT filename — must fail
                with pytest.raises(DuplicateDocumentError) as exc_info:
                    ingest_document(
                        db=db,
                        filename="catalog_final.pdf",
                        file_content=content,
                    )

            err = exc_info.value
            assert err.document_id == first_doc_id
            assert err.document_hash == result1["document_hash"]

            # Verify only ONE document row exists with this hash
            count = (
                db.query(Document)
                .filter(Document.document_hash == result1["document_hash"])
                .count()
            )
            assert count == 1, f"Expected 1 document, found {count}"

        finally:
            if first_doc_id is not None:
                doc = db.query(Document).filter(Document.id == first_doc_id).first()
                if doc:
                    db.delete(doc)
                    db.commit()
            db.close()

    def test_same_content_different_filename_is_duplicate(self, tmp_path):
        """
        catalog.pdf and catalog_final.pdf with identical binary content
        must be detected as duplicates.
        """
        from app.ingestion.service import ingest_document
        from app.ingestion.exceptions import DuplicateDocumentError
        from app.database.models import Document

        db = self._make_db_session()
        shared_content = self._make_minimal_pdf_bytes() + uuid.uuid4().bytes
        first_doc_id = None

        try:
            with patch("app.ingestion.service.process_document") as mock_proc:
                mock_proc.return_value = []

                result1 = ingest_document(
                    db=db,
                    filename="catalog.pdf",
                    file_content=shared_content,
                )
                first_doc_id = result1["document_id"]

                with pytest.raises(DuplicateDocumentError):
                    ingest_document(
                        db=db,
                        filename="catalog_final.pdf",
                        file_content=shared_content,
                    )

        finally:
            if first_doc_id is not None:
                doc = db.query(Document).filter(Document.id == first_doc_id).first()
                if doc:
                    db.delete(doc)
                    db.commit()
            db.close()

    def test_process_document_not_called_on_duplicate(self):
        """
        On a duplicate upload, process_document (extraction/chunking) must
        NOT be called.
        """
        from app.ingestion.service import ingest_document
        from app.ingestion.exceptions import DuplicateDocumentError
        from app.database.models import Document

        db = self._make_db_session()
        content = self._make_minimal_pdf_bytes() + uuid.uuid4().bytes
        first_doc_id = None

        try:
            with patch("app.ingestion.service.process_document") as mock_proc:
                mock_proc.return_value = []

                result1 = ingest_document(
                    db=db,
                    filename="first.pdf",
                    file_content=content,
                )
                first_doc_id = result1["document_id"]
                calls_after_first = mock_proc.call_count  # should be 1

                with pytest.raises(DuplicateDocumentError):
                    ingest_document(
                        db=db,
                        filename="second.pdf",
                        file_content=content,
                    )

                # process_document must NOT have been called again
                assert mock_proc.call_count == calls_after_first, (
                    "process_document was called on a duplicate upload — "
                    "expensive processing must be skipped!"
                )

        finally:
            if first_doc_id is not None:
                doc = db.query(Document).filter(Document.id == first_doc_id).first()
                if doc:
                    db.delete(doc)
                    db.commit()
            db.close()

    def test_different_content_both_processed_successfully(self):
        """Two documents with different content must both be ingested without error."""
        from app.ingestion.service import ingest_document
        from app.database.models import Document

        db = self._make_db_session()
        content_a = self._make_minimal_pdf_bytes() + uuid.uuid4().bytes
        content_b = self._make_minimal_pdf_bytes() + uuid.uuid4().bytes

        doc_id_a = doc_id_b = None
        try:
            with patch("app.ingestion.service.process_document") as mock_proc:
                mock_proc.return_value = []

                result_a = ingest_document(db=db, filename="doc_a.pdf", file_content=content_a)
                result_b = ingest_document(db=db, filename="doc_b.pdf", file_content=content_b)
                doc_id_a = result_a["document_id"]
                doc_id_b = result_b["document_id"]

            assert result_a["document_hash"] != result_b["document_hash"]

        finally:
            for doc_id in [doc_id_a, doc_id_b]:
                if doc_id is not None:
                    doc = db.query(Document).filter(Document.id == doc_id).first()
                    if doc:
                        db.delete(doc)
                        db.commit()
            db.close()


# ===========================================================================
# GROUP 3 — HTTP API tests (FastAPI TestClient)
# ===========================================================================

@pytest.mark.skipif(
    not _pg_ok,
    reason="DATABASE_URL not set — skipping HTTP duplicate-detection tests.",
)
class TestDuplicateDetectionAPI:
    """
    Tests the full HTTP upload endpoint for duplicate detection behavior.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.auth.dependencies import get_current_user
        from app.api.upload import get_db as upload_get_db
        from app.database.models import User

        admin_user = MagicMock(spec=User)
        admin_user.id = 9999
        admin_user.role = "ADMIN"

        def mock_db():
            yield MagicMock()

        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[upload_get_db] = mock_db
        c = TestClient(app, raise_server_exceptions=False)
        yield c
        app.dependency_overrides.clear()

    def _minimal_pdf(self) -> bytes:
        return b"%PDF-1.4 test " + uuid.uuid4().bytes

    def test_first_upload_returns_200(self, client):
        content = self._minimal_pdf()
        with patch("app.api.upload.ingest_document") as mock_ingest, \
             patch("app.api.upload.document_chunks_to_chunk_inputs") as mock_bridge, \
             patch("app.api.upload.index_chunks") as mock_index:

            mock_ingest.return_value = {
                "document_id": 1,
                "filename": "catalog.pdf",
                "document_hash": "a" * 64,
                "chunks": [],
            }
            mock_bridge.return_value = []
            mock_index.return_value = []

            resp = client.post(
                "/upload",
                files={"file": ("catalog.pdf", content, "application/pdf")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["document_hash"] == "a" * 64

    def test_duplicate_upload_returns_409(self, client):
        """Second upload with same content must return 409 Conflict."""
        from app.ingestion.exceptions import DuplicateDocumentError

        content = self._minimal_pdf()
        with patch("app.api.upload.ingest_document") as mock_ingest, \
             patch("app.api.upload.document_chunks_to_chunk_inputs"), \
             patch("app.api.upload.index_chunks"):

            mock_ingest.side_effect = DuplicateDocumentError(
                document_id=42,
                filename="catalog.pdf",
                document_hash="b" * 64,
            )

            resp = client.post(
                "/upload",
                files={"file": ("catalog_final.pdf", content, "application/pdf")},
            )

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["error"] == "duplicate_document"
        assert detail["existing_document_id"] == 42
        assert detail["document_hash"] == "b" * 64

    def test_duplicate_response_contains_existing_document_info(self, client):
        """409 response must include enough info to identify the original document."""
        from app.ingestion.exceptions import DuplicateDocumentError

        with patch("app.api.upload.ingest_document") as mock_ingest, \
             patch("app.api.upload.document_chunks_to_chunk_inputs"), \
             patch("app.api.upload.index_chunks"):

            mock_ingest.side_effect = DuplicateDocumentError(
                document_id=77,
                filename="original_catalog.pdf",
                document_hash="c" * 64,
            )

            resp = client.post(
                "/upload",
                files={"file": ("renamed_catalog.pdf", b"%PDF test", "application/pdf")},
            )

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["existing_document_id"] == 77
        assert detail["existing_filename"] == "original_catalog.pdf"
        assert detail["document_hash"] == "c" * 64
        assert "message" in detail

    def test_index_chunks_not_called_on_duplicate(self, client):
        """index_chunks (Qdrant indexing) must NOT be called for duplicate uploads."""
        from app.ingestion.exceptions import DuplicateDocumentError

        with patch("app.api.upload.ingest_document") as mock_ingest, \
             patch("app.api.upload.document_chunks_to_chunk_inputs") as mock_bridge, \
             patch("app.api.upload.index_chunks") as mock_index:

            mock_ingest.side_effect = DuplicateDocumentError(
                document_id=1,
                filename="existing.pdf",
                document_hash="d" * 64,
            )

            client.post(
                "/upload",
                files={"file": ("dup.pdf", b"%PDF dup", "application/pdf")},
            )

        mock_bridge.assert_not_called()
        mock_index.assert_not_called()


# ===========================================================================
# GROUP 4 — Concurrent duplicate upload (DB-level UNIQUE constraint)
# ===========================================================================

@pytest.mark.skipif(
    not _pg_ok,
    reason="DATABASE_URL not set — skipping concurrent upload test.",
)
class TestConcurrentDuplicateUpload:
    """
    Verifies the DB UNIQUE constraint prevents two simultaneous identical
    uploads from creating duplicate document records.
    """

    def test_concurrent_identical_uploads_create_at_most_one_record(self):
        """
        Two threads uploading the exact same bytes simultaneously must result
        in exactly one Document record in the database.
        """
        from app.database.session import SessionLocal
        from app.database.models import Document
        from app.ingestion.service import ingest_document
        from app.ingestion.exceptions import DuplicateDocumentError

        content = b"%PDF-1.4 concurrent test " + uuid.uuid4().bytes
        results = []
        errors = []

        def upload_worker():
            db = SessionLocal()
            try:
                with patch("app.ingestion.service.process_document") as mock_proc:
                    mock_proc.return_value = []
                    result = ingest_document(
                        db=db,
                        filename=f"concurrent_{uuid.uuid4().hex}.pdf",
                        file_content=content,
                    )
                results.append(result["document_id"])
            except DuplicateDocumentError as e:
                errors.append(("duplicate", e.document_hash))
            except Exception as e:
                errors.append(("error", str(e)))
            finally:
                db.close()

        threads = [threading.Thread(target=upload_worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At most one success; the other must be a duplicate or error
        total_successes = len(results)
        assert total_successes <= 1, (
            f"Both concurrent uploads succeeded! Document IDs: {results}. "
            "The UNIQUE constraint must have prevented a duplicate."
        )

        # Verify at most one DB row with this hash
        import hashlib
        # Write to temp file to get hash
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            expected_hash = hashlib.sha256(content).hexdigest()
            db = SessionLocal()
            count = (
                db.query(Document)
                .filter(Document.document_hash == expected_hash)
                .count()
            )
            # Cleanup
            doc = db.query(Document).filter(
                Document.document_hash == expected_hash
            ).first()
            if doc:
                db.delete(doc)
                db.commit()
            db.close()
        finally:
            os.unlink(temp_path)

        assert count <= 1, (
            f"Found {count} document rows with the same hash — "
            "concurrent duplicate prevention failed!"
        )


# ===========================================================================
# GROUP 5 — DuplicateDocumentError unit tests
# ===========================================================================

class TestDuplicateDocumentError:
    """Unit tests for the DuplicateDocumentError exception class."""

    def test_attributes_are_set_correctly(self):
        from app.ingestion.exceptions import DuplicateDocumentError

        err = DuplicateDocumentError(
            document_id=42,
            filename="catalog.pdf",
            document_hash="a" * 64,
        )
        assert err.document_id == 42
        assert err.filename == "catalog.pdf"
        assert err.document_hash == "a" * 64

    def test_str_contains_document_id(self):
        from app.ingestion.exceptions import DuplicateDocumentError

        err = DuplicateDocumentError(42, "f.pdf", "a" * 64)
        assert "42" in str(err)

    def test_is_exception_subclass(self):
        from app.ingestion.exceptions import DuplicateDocumentError

        err = DuplicateDocumentError(1, "x.pdf", "b" * 64)
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self):
        from app.ingestion.exceptions import DuplicateDocumentError

        with pytest.raises(DuplicateDocumentError) as exc_info:
            raise DuplicateDocumentError(99, "doc.pdf", "c" * 64)
        assert exc_info.value.document_id == 99
