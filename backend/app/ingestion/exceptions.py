"""
app/ingestion/exceptions.py

Domain-specific exceptions for the document ingestion pipeline.
"""


class DuplicateDocumentError(Exception):
    """
    Raised when an uploaded file's SHA-256 content hash already exists
    in the database, indicating the binary contents are identical to a
    previously ingested document.

    Attributes
    ----------
    document_id : int
        Database ID of the existing document that matched the hash.
    filename : str
        Original filename of the existing document record.
    document_hash : str
        The 64-character SHA-256 digest that was matched.
    """

    def __init__(
        self,
        document_id: int,
        filename: str,
        document_hash: str,
    ) -> None:
        self.document_id = document_id
        self.filename = filename
        self.document_hash = document_hash
        super().__init__(
            f"Duplicate document detected: the uploaded file's content matches "
            f"existing document ID {document_id} ('{filename}'). "
            f"SHA-256: {document_hash}"
        )
