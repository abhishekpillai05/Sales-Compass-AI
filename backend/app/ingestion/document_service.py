"""
app/ingestion/document_service.py

PostgreSQL document-record operations for the ingestion pipeline.

Provides:
- ``create_document_record`` — insert a new document row (with hash).
- ``find_document_by_hash``  — look up an existing document by its
  SHA-256 content hash; used for duplicate detection.
"""

from sqlalchemy.orm import Session

from app.database.models import Document


def create_document_record(
    db: Session,
    filename: str,
    uploaded_by: int | None = None,
    document_hash: str | None = None,
) -> Document:
    """
    Create a document record in PostgreSQL.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    filename : str
        Original filename provided by the uploader.
    uploaded_by : int or None
        ID of the user who performed the upload; ``None`` if anonymous.
    document_hash : str or None
        64-character SHA-256 hexadecimal digest of the file's raw bytes.
        Pass ``None`` only for legacy ingestion paths where hashing is
        not available.

    Returns
    -------
    Document
        The newly created and database-refreshed ORM instance.
    """
    document = Document(
        filename=filename,
        uploaded_by=uploaded_by,
        document_hash=document_hash,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def find_document_by_hash(
    db: Session,
    document_hash: str,
) -> Document | None:
    """
    Look up an existing document record by its SHA-256 content hash.

    Used for application-level duplicate detection **before** attempting
    an INSERT, giving callers a clean, user-friendly response instead of
    a raw database integrity error.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    document_hash : str
        64-character SHA-256 hexadecimal digest to search for.

    Returns
    -------
    Document or None
        The matching ``Document`` ORM instance if a duplicate exists,
        otherwise ``None``.
    """
    return (
        db.query(Document)
        .filter(Document.document_hash == document_hash)
        .first()
    )