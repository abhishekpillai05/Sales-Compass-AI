"""
app/api/upload.py

Document upload endpoint.

POST /upload
    Requires ADMIN role.
    Accepts a multipart file upload, runs the full ingestion + indexing
    pipeline, and returns a structured result.

Duplicate documents (same binary content, detected via SHA-256 hash)
are rejected **before** any extraction, embedding, or Qdrant indexing
with a ``409 Conflict`` response that identifies the existing document.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models import User
from app.auth.dependencies import require_role
from app.auth.roles import UserRole
from app.ingestion.exceptions import DuplicateDocumentError
from app.ingestion.service import ingest_document
from app.ingestion.bridge import document_chunks_to_chunk_inputs
from app.knowledge_indexing import index_chunks
from app.logging.config import get_logger


logger = get_logger(__name__)

router = APIRouter(
    prefix="/upload",
    tags=["Document Ingestion"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN.value)),
):
    """
    Upload and process a PDF, Excel, or CSV document.

    Full pipeline:
      Phase 3 (Ingestion) → Phase 4 (Knowledge Indexing → Qdrant + PostgreSQL)

    Duplicate Detection
    -------------------
    If the uploaded file's binary content is identical to an already-indexed
    document (detected via SHA-256 hash), the endpoint returns ``409 Conflict``
    without running extraction, chunking, embedding, or Qdrant indexing.
    """

    try:

        logger.info("upload started filename=%s", file.filename)

        file_content = await file.read()

        # ── Phase 3: Ingestion ──────────────────────────────────────────────
        result = ingest_document(
            db=db,
            filename=file.filename,
            file_content=file_content,
            uploaded_by=current_user.id,
        )

        document_chunks = result["chunks"]

        # ── Phase 4: Knowledge Indexing (Bridge → Qdrant + PostgreSQL) ──────
        chunk_inputs = document_chunks_to_chunk_inputs(document_chunks)
        indexing_results = index_chunks(chunk_inputs)

        indexed_count = sum(1 for r in indexing_results if r.success)
        failed_count = len(indexing_results) - indexed_count
        indexing_errors = [
            {"chunk_id": r.chunk_id, "error": r.error}
            for r in indexing_results
            if not r.success
        ]

        logger.info(
            "upload completed filename=%s document_id=%s document_hash=%s "
            "chunks_created=%d chunks_indexed=%d chunks_failed=%d",
            file.filename,
            result["document_id"],
            result.get("document_hash", "n/a"),
            len(document_chunks),
            indexed_count,
            failed_count,
        )

        return {
            "success": True,
            "document_id": result["document_id"],
            "filename": result["filename"],
            "document_hash": result.get("document_hash"),
            "chunks_created": len(document_chunks),
            "chunks_indexed": indexed_count,
            "chunks_index_failed": failed_count,
            "indexing_errors": indexing_errors,
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                }
                for chunk in document_chunks
            ],
        }

    except DuplicateDocumentError as e:

        logger.info(
            "duplicate upload rejected filename=%s "
            "existing_document_id=%s hash=%s",
            file.filename,
            e.document_id,
            e.document_hash,
        )

        raise HTTPException(
            status_code=409,
            detail={
                "error": "duplicate_document",
                "message": (
                    "The uploaded file's content is identical to an existing document. "
                    "No reprocessing was performed."
                ),
                "existing_document_id": e.document_id,
                "existing_filename": e.filename,
                "document_hash": e.document_hash,
            },
        )

    except ValueError as e:

        logger.warning("upload validation error filename=%s error=%s", file.filename, str(e))

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:

        logger.error(
            "upload unexpected error filename=%s error_type=%s message=%s",
            file.filename,
            type(e).__name__,
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {str(e)}",
        )
