"""
app/ingestion/hasher.py

Deterministic SHA-256 content hashing service for uploaded documents.

Design principles:
- Hashes only the raw binary bytes of the file on disk.
- Completely independent of filename, path, timestamp, user ID, or any
  mutable metadata — two files with identical bytes always produce the
  same 64-character hexadecimal digest.
- File-type agnostic: works for PDF, DOCX, XLSX, CSV, TXT, and any
  other binary format.
- Uses incremental (chunked) reading to avoid loading large files into
  memory all at once.
- Does NOT perform parsing, OCR, text extraction, chunking, embedding,
  or any database I/O.
- Propagates filesystem errors (FileNotFoundError, PermissionError) to
  the caller; swallows nothing silently.
- Empty files are valid: SHA-256 of zero bytes is a well-defined,
  deterministic value.
"""

import hashlib
from pathlib import Path

# Read the file in 64 KB increments.  Large enough to keep syscall
# overhead low; small enough to keep peak memory usage modest regardless
# of file size.
_CHUNK_SIZE: int = 64 * 1024  # 64 KB


def calculate_file_hash(file_path: str | Path) -> str:
    """
    Calculate a deterministic SHA-256 hash of the file's binary contents.

    The hash depends **only** on the raw bytes of the file.  It is
    completely independent of the filename, storage path, upload
    timestamp, user ID, or any other metadata.

    Parameters
    ----------
    file_path : str or Path
        Absolute or relative path to the file on disk.

    Returns
    -------
    str
        A 64-character lowercase hexadecimal SHA-256 digest, e.g.
        ``"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"``.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    PermissionError
        If the process lacks read permission for *file_path*.
    OSError
        For other filesystem-level errors (I/O error, network share
        unavailable, etc.).

    Notes
    -----
    * An empty file is valid input and returns the canonical SHA-256 of
      zero bytes — ``e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855``.
    * The function reads the file in ``_CHUNK_SIZE``-byte increments so
      it is safe to use with arbitrarily large files without exhausting
      memory.
    """
    file_path = Path(file_path)

    hash_object = hashlib.sha256()

    with open(file_path, "rb") as file:
        while chunk := file.read(_CHUNK_SIZE):
            hash_object.update(chunk)

    return hash_object.hexdigest()
