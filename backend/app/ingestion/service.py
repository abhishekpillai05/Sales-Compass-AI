"""
app/ingestion/service.py

Complete document ingestion orchestrator.

Pipeline order (duplicate detection is intentionally early to avoid
expensive downstream work for files that are already indexed):

  1. Validate          — extension, size
  2. Save file         — write bytes to uploads/original/<uuid>.<ext>
  3. Hash              — SHA-256 of saved file bytes (binary, content-only)
  4. Duplicate check   — query DB for existing document_hash
                         → raise DuplicateDocumentError if found
                         → clean up saved file (no orphaned files)
  5. Create DB record  — Document row with document_hash
  6. Process           — extract text → clean → chunk → metadata
  7. Return            — structured result with chunks

Concurrency safety
------------------
Step 4 is the application-level check for a user-friendly error.
The database UNIQUE constraint on Document.document_hash provides the
authoritative last line of defence: if two concurrent uploads for the
same content race past step 4 simultaneously, the second INSERT will
raise ``sqlalchemy.exc.IntegrityError`` (unique constraint violation),
which is caught here and re-raised as ``DuplicateDocumentError``.
"""

from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ingestion.document_service import create_document_record, find_document_by_hash
from app.ingestion.exceptions import DuplicateDocumentError
from app.ingestion.hasher import calculate_file_hash
from app.ingestion.pipeline import process_document
from app.ingestion.upload import save_file
from app.ingestion.validators import validate_file
from app.logging.config import get_logger


logger = get_logger(__name__)


def ingest_document(
    db: Session,
    filename: str,
    file_content: bytes,
    uploaded_by: int | None = None,
):
    """
    Complete document ingestion flow.

    Steps
    -----
    1. Validate extension and size.
    2. Save original file to disk (deterministic UUID-named path).
    3. Calculate SHA-256 content hash of the saved file.
    4. Check for duplicate: if hash already exists → raise
       ``DuplicateDocumentError`` without running extraction/indexing.
    5. Create PostgreSQL document record (with hash).
    6. Extract, clean, chunk and extract metadata.
    7. Return structured result.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy database session.
    filename : str
        Original filename supplied by the uploader.
    file_content : bytes
        Raw binary content of the uploaded file.
    uploaded_by : int or None
        ID of the uploading user; ``None`` for anonymous/system uploads.

    Returns
    -------
    dict
        Keys: ``document_id``, ``filename``, ``file_path``,
        ``document_hash``, ``chunks``.

    Raises
    ------
    ValueError
        If file validation fails (bad extension, size limit exceeded, etc.).
    DuplicateDocumentError
        If the file's binary content is identical to an already-indexed
        document (detected via SHA-256 hash).
    Exception
        Any other error during extraction/chunking; the DB record and
        saved file are cleaned up before re-raising.
    """

    # ------------------------------------------------------------------
    # 1. Validate
    # ------------------------------------------------------------------

    validate_file(
        filename=filename,
        file_size=len(file_content),
    )

    file_path = None
    document = None

    try:

        # ------------------------------------------------------------------
        # 2. Save original file
        # ------------------------------------------------------------------

        file_path = save_file(
            filename=filename,
            file_content=file_content,
        )

        # ------------------------------------------------------------------
        # 3. Calculate SHA-256 content hash
        #    Must be done BEFORE create_document_record so we can gate
        #    duplicate uploads before any DB writes.
        # ------------------------------------------------------------------

        document_hash = calculate_file_hash(file_path)

        logger.debug(
            "content hash calculated filename=%s hash=%s",
            filename,
            document_hash,
        )

        # ------------------------------------------------------------------
        # 4. Application-level duplicate check
        #    Provides a clean user-facing response for the common case.
        #    The DB UNIQUE constraint covers the concurrent-upload edge case.
        # ------------------------------------------------------------------

        existing = find_document_by_hash(db=db, document_hash=document_hash)

        if existing is not None:
            # Remove the newly saved file — there is no point keeping a
            # byte-for-byte copy of something already indexed.
            _remove_file_if_exists(file_path)

            logger.info(
                "duplicate upload detected filename=%s "
                "existing_document_id=%s hash=%s",
                filename,
                existing.id,
                document_hash,
            )

            raise DuplicateDocumentError(
                document_id=existing.id,
                filename=existing.filename,
                document_hash=document_hash,
            )

        # ------------------------------------------------------------------
        # 5. Create PostgreSQL record (with hash)
        # ------------------------------------------------------------------

        try:
            document = create_document_record(
                db=db,
                filename=filename,
                uploaded_by=uploaded_by,
                document_hash=document_hash,
            )
        except IntegrityError:
            # Concurrent upload raced past the application-level check.
            # The UNIQUE constraint fired; treat it as a duplicate.
            db.rollback()

            _remove_file_if_exists(file_path)

            # Re-query to get the winning document's details.
            existing = find_document_by_hash(db=db, document_hash=document_hash)

            logger.warning(
                "concurrent duplicate upload detected filename=%s "
                "existing_document_id=%s hash=%s",
                filename,
                existing.id if existing else "unknown",
                document_hash,
            )

            raise DuplicateDocumentError(
                document_id=existing.id if existing else -1,
                filename=existing.filename if existing else filename,
                document_hash=document_hash,
            )

        # ------------------------------------------------------------------
        # 6. Process document (extract → clean → chunk → metadata)
        # ------------------------------------------------------------------

        chunks = process_document(
            file_path=file_path,
            document_id=document.id,
        )

        # ------------------------------------------------------------------
        # 7. Return result
        # ------------------------------------------------------------------

        return {
            "document_id": document.id,
            "filename": document.filename,
            "file_path": str(file_path),
            "document_hash": document_hash,
            "chunks": chunks,
        }

    except DuplicateDocumentError:
        # Let DuplicateDocumentError propagate unchanged — the caller
        # (upload API) handles it with a specific HTTP response.
        raise

    except Exception:

        # Rollback current database transaction
        db.rollback()

        # Remove database record if it was created
        if document is not None:
            db.delete(document)
            db.commit()

        # Remove saved file if it exists
        _remove_file_if_exists(file_path)

        raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _remove_file_if_exists(file_path) -> None:
    """Delete *file_path* from disk if it exists. Silences missing-file errors."""
    if file_path is not None:
        path = Path(file_path)
        if path.exists():
            path.unlink()